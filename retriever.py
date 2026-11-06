"""Retrieval for the PawPal+ Care Advisor (RAG).

Pet-care documents in knowledge/ are split into chunks at each "## " heading.
A chunk may start with "key: value" lines (species, topic, recommended_minutes, ...)
that are parsed into structured hints. Chunks are ranked against a query with
TF-IDF cosine similarity, written in plain Python so there are no extra dependencies.
"""

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is", "are", "be",
    "it", "its", "at", "as", "by", "with", "that", "this", "can", "should", "from",
    "i", "my", "me", "do", "does", "how", "what", "when", "often", "much", "many",
}


@dataclass
class Chunk:
    """One section of a knowledge document."""

    source: str  # file name, e.g. "dog_care.md"
    title: str  # the "## " heading
    text: str  # body text without the key: value lines
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class Hit:
    """A retrieved chunk and how well it matched (0.0 to 1.0)."""

    chunk: Chunk
    score: float


def tokenize(text: str) -> List[str]:
    """Lowercase, split into words, drop stopwords and apply a tiny stemmer."""
    tokens = []
    for word in re.findall(r"[a-z]+", text.lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        if word.endswith("ies") and len(word) > 4:
            word = word[:-3] + "y"  # puppies -> puppy
        else:
            for suffix in ("ing", "es", "ed", "s"):
                if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                    word = word[: -len(suffix)]
                    break
        tokens.append(word)
    return tokens


def parse_document(source: str, raw: str) -> List[Chunk]:
    """Split one markdown document into chunks and parse their key: value hints."""
    chunks: List[Chunk] = []
    title: Optional[str] = None
    lines: List[str] = []

    def flush() -> None:
        if title is None:
            return
        meta: Dict[str, str] = {}
        body: List[str] = []
        for line in lines:
            match = re.fullmatch(r"([a-z_]+):\s*(.+)", line.strip())
            if match and not body:
                meta[match.group(1)] = match.group(2).strip()
            elif line.strip():
                body.append(line.strip())
        if body:
            chunks.append(Chunk(source, title, " ".join(body), meta))

    for line in raw.splitlines():
        if line.startswith("## "):
            flush()
            title, lines = line[3:].strip(), []
        elif title is not None:
            lines.append(line)
    flush()
    return chunks


class KnowledgeBase:
    """Loads knowledge documents and answers similarity searches."""

    def __init__(self, directory: str = KNOWLEDGE_DIR):
        self.chunks: List[Chunk] = []
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"knowledge directory not found: {directory}")
        for name in sorted(os.listdir(directory)):
            if name.endswith(".md"):
                with open(os.path.join(directory, name), encoding="utf-8") as f:
                    self.chunks.extend(parse_document(name, f.read()))
        if not self.chunks:
            raise ValueError(f"no knowledge chunks found in {directory}")
        self._build_index()

    def _chunk_tokens(self, chunk: Chunk) -> List[str]:
        # title and topic are repeated so they weigh more than body words
        extra = f"{chunk.title} {chunk.meta.get('topic', '')} {chunk.meta.get('species', '')}"
        return tokenize(f"{chunk.title} {chunk.text} {extra}")

    def _build_index(self) -> None:
        docs = [Counter(self._chunk_tokens(c)) for c in self.chunks]
        n = len(docs)
        df: Counter = Counter()
        for counts in docs:
            df.update(counts.keys())
        self.idf = {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}
        self.vectors = [self._weigh(counts) for counts in docs]

    def _weigh(self, counts: Counter) -> Dict[str, float]:
        vec = {t: c * self.idf.get(t, 1.0) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, k: int = 3, species: Optional[str] = None) -> List[Hit]:
        """Return up to k chunks ranked by cosine similarity (best first).

        If `species` is given, chunks for other species are ranked lower; chunks
        marked species "any" are always allowed.
        """
        q_counts = Counter(tokenize(query))
        if not q_counts:
            return []
        q_vec = self._weigh(q_counts)
        hits = []
        for chunk, vec in zip(self.chunks, self.vectors):
            score = sum(weight * vec.get(term, 0.0) for term, weight in q_vec.items())
            chunk_species = chunk.meta.get("species")
            if species and chunk_species and chunk_species not in (species, "any"):
                score *= 0.3
            if score > 0:
                hits.append(Hit(chunk, round(score, 4)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def for_species_topic(self, species: str, topic: str) -> Optional[Chunk]:
        """Return the chunk tagged with this exact species and topic, if there is one."""
        for chunk in self.chunks:
            if chunk.meta.get("species") == species and chunk.meta.get("topic") == topic:
                return chunk
        for chunk in self.chunks:
            if chunk.meta.get("species") == "any" and chunk.meta.get("topic") == topic:
                return chunk
        return None
