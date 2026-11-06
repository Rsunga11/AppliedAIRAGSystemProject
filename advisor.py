"""PawPal+ Care Advisor: answers questions and reviews tasks using retrieved guidance (RAG).

Retrieval drives behavior here: the numbers used to review a task or propose a
routine are parsed from the knowledge chunks that were retrieved, not hard-coded.
Guardrails: dosage/diagnosis/emergency questions are refused with a vet referral,
low-confidence answers are flagged for review, and everything is logged.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

from pawpal_system import Pet, Task
from retriever import Chunk, Hit, KnowledgeBase

logger = logging.getLogger("pawpal")
logger.addHandler(logging.NullHandler())  # stay quiet unless configure_logging() is called
_file_logging_enabled = False

LOW_CONFIDENCE = 0.5  # below this, results are marked "needs review"
MIN_RETRIEVAL_SCORE = 0.2  # below this, we say we don't know instead of guessing
MAX_QUESTION_LENGTH = 500

VET_DISCLAIMER = (
    "I can't give medical advice, dosages or diagnoses. Please contact a licensed veterinarian. "
    "In an emergency, call an emergency vet or an animal poison control hotline right away."
)
# Questions matching these must never be answered from the knowledge base.
UNSAFE_PATTERN = re.compile(
    r"\b(dose|dosage|dosing|overdose|mg|milligram|how much (medicine|medication|ibuprofen|tylenol|aspirin)"
    r"|diagnos\w*|symptom\w*|vomit\w*|bleed\w*|seizure\w*|limp\w*|poison\w*|emergency|sick|infection)\b",
    re.IGNORECASE,
)

TOPIC_KEYWORDS = {
    "walk": ("walk", "jog", "run "),
    "feeding": ("feed", "breakfast", "dinner", "lunch", "meal", "food"),
    "grooming": ("groom", "brush", "bath"),
    "play": ("play", "fetch", "toy", "enrich", "train"),
    "vet": ("vet", "checkup", "appointment"),
    "medication": ("medic", "pill", "dose"),
    "flea": ("flea", "tick"),
    "litter": ("litter", "scoop"),
}
# Routine topics PawPal+ will propose, with priority and default frequency.
PROPOSAL_PRIORITY = {"feeding": "high", "walk": "high", "play": "medium", "litter": "medium"}
PROPOSAL_LABEL = {"walk": "walk", "feeding": "feeding", "play": "play session", "litter": "litter box scoop"}
PROPOSAL_TIMES = {1: ["18:00"], 2: ["07:30", "18:00"], 3: ["07:30", "12:30", "18:00"]}


def configure_logging(path: str = "logs/pawpal.log") -> None:
    """Send PawPal+ logs to a file (idempotent). Never log API keys or secrets."""
    global _file_logging_enabled
    if _file_logging_enabled:
        return
    _file_logging_enabled = True
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@dataclass
class Guidance:
    """Structured hints parsed from a retrieved knowledge chunk."""

    species: str
    topic: str
    min_minutes: Optional[int]
    max_minutes: Optional[int]
    per_day: int
    source: str
    title: str
    confidence: float


@dataclass
class Review:
    """Result of checking one task against retrieved guidance."""

    status: str  # "ok", "warn" or "unknown"
    messages: List[str]
    confidence: float
    sources: List[str]

    @property
    def needs_review(self) -> bool:
        return self.confidence < LOW_CONFIDENCE


@dataclass
class Answer:
    """Result of answering a free-text question."""

    text: str
    confidence: float
    sources: List[str]
    refused: bool = False
    used_llm: bool = False

    @property
    def needs_review(self) -> bool:
        return self.confidence < LOW_CONFIDENCE


@dataclass
class Proposal:
    """A task the advisor suggests. Nothing is added until a human approves it."""

    description: str
    time: str
    duration_minutes: int
    priority: str
    frequency: str
    topic: str
    source: str
    confidence: float
    due: Optional[date] = None  # None means "today"

    def to_task(self) -> Task:
        """Build the real Task for this proposal (call only after approval)."""
        task = Task(self.description, self.time, self.duration_minutes, self.priority, self.frequency)
        if self.due is not None:
            task.due_date = self.due
        return task


def detect_topic(description: str) -> Optional[str]:
    """Guess a care topic (walk, feeding, ...) from a task description."""
    text = f"{description.lower()} "
    for topic, words in TOPIC_KEYWORDS.items():
        if any(w in text for w in words):
            return topic
    return None


def _parse_range(value: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """Turn '30-60' into (30, 60) and '10' into (10, 10)."""
    if not value:
        return None, None
    nums = [int(n) for n in re.findall(r"\d+", value)]
    if not nums:
        return None, None
    return nums[0], nums[-1]


def _confidence(hit: Hit, topic_matches: bool) -> float:
    """Combine retrieval score and topic agreement into a 0-1 confidence."""
    return round(min(0.95, hit.score * 1.2 + (0.2 if topic_matches else 0.0)), 2)  # never claims certainty


class CareAdvisor:
    """Retrieval-backed advisor. `llm` is optional (anything with explain(question, snippets))."""

    def __init__(self, kb: Optional[KnowledgeBase] = None, llm=None):
        self.kb = kb or KnowledgeBase()
        self.llm = llm

    # ---------------------------------------------------------------- guidance
    def guidance_for(self, species: str, description: str) -> Optional[Guidance]:
        """Retrieve the best guidance chunk for a task and parse its numbers."""
        topic = detect_topic(description)
        if topic is None:
            return None  # unknown kind of task: say "unknown" rather than guess
        query = f"{species} {topic} {description}"
        for hit in self.kb.search(query, k=5, species=species):
            meta = hit.chunk.meta
            if "recommended_minutes" not in meta or meta.get("topic") != topic:
                continue
            low, high = _parse_range(meta.get("recommended_minutes"))
            _, per_day = _parse_range(meta.get("recommended_per_day"))
            return Guidance(
                species=meta.get("species", species),
                topic=meta.get("topic", topic or ""),
                min_minutes=low,
                max_minutes=high,
                per_day=per_day or 0,
                source=hit.chunk.source,
                title=hit.chunk.title,
                confidence=_confidence(hit, topic == meta.get("topic")),
            )
        return None

    # ------------------------------------------------------------ task review
    def review_task(self, pet: Pet, task: Task) -> Review:
        """Check a task's duration against guidance retrieved for the pet's species."""
        guidance = self.guidance_for(pet.species, task.description)
        if guidance is None:
            logger.info("review pet=%s task=%r status=unknown (no guidance)", pet.name, task.description)
            return Review("unknown", ["No care guidance found for this task."], 0.0, [])

        messages = []
        if guidance.min_minutes and task.duration_minutes < guidance.min_minutes:
            messages.append(
                f"{task.duration_minutes} min is shorter than the usual {guidance.min_minutes}-{guidance.max_minutes} min "
                f"for a {pet.species} ({guidance.title})."
            )
        if guidance.max_minutes and task.duration_minutes > guidance.max_minutes * 2:
            messages.append(
                f"{task.duration_minutes} min is much longer than the usual {guidance.min_minutes}-{guidance.max_minutes} min "
                f"({guidance.title})."
            )
        status = "warn" if messages else "ok"
        if not messages:
            messages.append(f"Looks reasonable for a {pet.species} ({guidance.title}).")
        source = f"{guidance.source}: {guidance.title}"
        logger.info(
            "review pet=%s task=%r status=%s confidence=%.2f source=%s",
            pet.name, task.description, status, guidance.confidence, source,
        )
        return Review(status, messages, guidance.confidence, [source])

    # -------------------------------------------------------------- questions
    def answer_question(self, question: str, species: Optional[str] = None) -> Answer:
        """Answer a care question from retrieved documents, with guardrails and a confidence score."""
        try:
            question = (question or "").strip()
            if not question:
                return Answer("Please type a question.", 0.0, [], refused=True)
            if len(question) > MAX_QUESTION_LENGTH:
                return Answer(f"Please keep questions under {MAX_QUESTION_LENGTH} characters.", 0.0, [], refused=True)
            if UNSAFE_PATTERN.search(question):
                logger.warning("guardrail: refused medical question")
                return Answer(VET_DISCLAIMER, 1.0, ["medication_and_vet_safety.md: Dosage and diagnosis questions"], refused=True)

            hits = self.kb.search(question, k=3, species=species)
            if not hits or hits[0].score < MIN_RETRIEVAL_SCORE:
                logger.info("answer: no reliable match for question")
                return Answer(
                    "I couldn't find reliable guidance for that in my pet-care notes. "
                    "Please ask a veterinarian or check a trusted pet-care source.",
                    round(hits[0].score if hits else 0.0, 2),
                    [],
                )

            sources = [f"{h.chunk.source}: {h.chunk.title}" for h in hits]
            confidence = _confidence(hits[0], True)
            text = self._compose_offline(hits[0].chunk)
            used_llm = False
            if self.llm is not None:
                snippets = [h.chunk.text for h in hits]
                generated = self.llm.explain(question, snippets)
                if generated:
                    text, used_llm = generated, True
            logger.info("answer: confidence=%.2f used_llm=%s top_source=%s", confidence, used_llm, sources[0])
            return Answer(text, confidence, sources, used_llm=used_llm)
        except Exception:  # never crash the app because of one bad question
            logger.exception("answer_question failed")
            return Answer("Sorry, something went wrong answering that. Please try again.", 0.0, [], refused=True)

    @staticmethod
    def _compose_offline(chunk: Chunk) -> str:
        """Offline answer: the first two sentences of the best chunk."""
        sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
        return " ".join(sentences[:2])

    # ------------------------------------------------------------- proposals
    def recommend_tasks(self, pet: Pet) -> List[Proposal]:
        """Propose routine tasks for this pet's species that it doesn't already have."""
        proposals: List[Proposal] = []
        covered = {detect_topic(t.description) for t in pet.tasks}
        for chunk in self.kb.chunks:
            meta = chunk.meta
            topic = meta.get("topic")
            if meta.get("species") != pet.species or topic not in PROPOSAL_PRIORITY or topic in covered:
                continue
            low, high = _parse_range(meta.get("recommended_minutes"))
            _, per_day = _parse_range(meta.get("recommended_per_day"))
            if not per_day or low is None:
                continue
            duration = (low + high) // 2
            guidance = self.guidance_for(pet.species, PROPOSAL_LABEL[topic])
            confidence = guidance.confidence if guidance else 0.5
            for index, time in enumerate(PROPOSAL_TIMES.get(per_day, PROPOSAL_TIMES[2])[:per_day]):
                part = "Morning " if time < "12:00" else "Evening " if time >= "17:00" else "Midday "
                label = PROPOSAL_LABEL[topic]
                description = f"{part if per_day > 1 else ''}{label}".strip().capitalize()
                proposals.append(
                    Proposal(description, time, duration, PROPOSAL_PRIORITY[topic], "daily", topic,
                             f"{chunk.source}: {chunk.title}", confidence)
                )
        logger.info("recommend pet=%s proposals=%d", pet.name, len(proposals))
        return proposals
