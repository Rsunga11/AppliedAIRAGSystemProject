"""PawPal+ Care Plan Agent: plan -> act -> check -> re-plan.

For one pet the agent
  1. PLANS: asks the advisor (RAG) which routine tasks the pet is missing,
  2. ACTS: tries them in a scratch copy of the owner's data (the real data is untouched),
  3. CHECKS: looks for conflicts and overlapping durations, and reviews each task against retrieved guidance,
  4. RE-PLANS: moves conflicting tasks to the next free slot and checks again (up to max_rounds).
It only PROPOSES. A human must approve before apply() adds anything to the real pet.
"""

import copy
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from advisor import LOW_CONFIDENCE, CareAdvisor, Proposal, logger
from pawpal_system import Owner, Pet, Scheduler, to_minutes


@dataclass
class AgentResult:
    """What the agent decided, plus the reasoning trace that led there."""

    pet_name: str
    proposals: List[Proposal]
    trace: List[Dict[str, object]]
    unresolved: List[str] = field(default_factory=list)
    rounds: int = 0

    @property
    def confidence(self) -> float:
        """The agent is only as confident as its least confident proposal (0 if there are none)."""
        return min((p.confidence for p in self.proposals), default=0.0)

    @property
    def needs_review(self) -> bool:
        return bool(self.unresolved) or self.confidence < LOW_CONFIDENCE


def find_overlaps(owner: Owner, day: date) -> List[str]:
    """Return messages for open tasks on `day` whose time ranges overlap (catches more than exact-time matches)."""
    items = []
    for pet in owner.pets:
        for task in pet.tasks:
            if task.due_date == day and not task.completed:
                start = to_minutes(task.time)
                items.append((start, start + task.duration_minutes, pet.name, task.description))
    items.sort()
    messages = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[j][0] >= items[i][1]:
                break  # sorted by start, so nothing later can overlap item i
            messages.append(
                f"{items[i][3]} ({items[i][2]}) overlaps {items[j][3]} ({items[j][2]}) around {items[j][0] // 60:02d}:{items[j][0] % 60:02d}"
            )
    return messages


class CarePlanAgent:
    """Plans a routine for a pet, checks its own work, and fixes problems before proposing."""

    def __init__(self, advisor: CareAdvisor, max_rounds: int = 3):
        self.advisor = advisor
        self.max_rounds = max_rounds

    def run(self, owner: Owner, pet: Pet, day: Optional[date] = None) -> AgentResult:
        """Plan, act and check for `pet`. Never changes `owner`; returns proposals and a trace."""
        if all(p is not pet for p in owner.pets):
            raise ValueError(f"{pet.name} does not belong to this owner")
        day = day or date.today()
        trace: List[Dict[str, object]] = []

        def log(round_no: int, phase: str, detail: str) -> None:
            trace.append({"step": len(trace) + 1, "round": round_no, "phase": phase, "detail": detail})
            logger.info("agent pet=%s round=%d phase=%s %s", pet.name, round_no, phase, detail)

        # ---- PLAN
        proposals = self.advisor.recommend_tasks(pet)
        for p in proposals:
            p.due = day
        if not proposals:
            log(0, "plan", f"{pet.name} ({pet.species}) already has every routine task I know about, or I have no guidance.")
            return AgentResult(pet.name, [], trace, rounds=0)
        log(0, "plan", f"Retrieved guidance for {pet.species}; proposing {len(proposals)} task(s): "
                       + ", ".join(f"{p.description} @ {p.time}" for p in proposals))

        # ---- ACT / CHECK / RE-PLAN loop, on a scratch copy of the data
        scratch = copy.deepcopy(owner)
        scratch_pet = next(p for p in scratch.pets if p.name == pet.name)
        placed = {}
        for p in proposals:
            task = p.to_task()
            scratch_pet.add_task(task)
            placed[id(p)] = task
        log(0, "act", "Placed all proposals at their preferred times in a scratch copy (real data untouched).")

        unresolved: List[str] = []
        rounds = 0
        for rounds in range(1, self.max_rounds + 1):
            scheduler = Scheduler(scratch)
            problems = scheduler.find_conflicts() + find_overlaps(scratch, day)
            if not problems:
                log(rounds, "check", "No conflicts or overlaps. Plan is consistent.")
                break
            log(rounds, "check", f"{len(problems)} problem(s): " + " | ".join(problems))
            moved = 0
            for p in proposals:
                task = placed[id(p)]
                others_overlap = any(
                    t is not task and t.due_date == day and not t.completed
                    and to_minutes(t.time) < to_minutes(task.time) + task.duration_minutes
                    and to_minutes(task.time) < to_minutes(t.time) + t.duration_minutes
                    for t in scratch.get_all_tasks()
                )
                if not others_overlap:
                    continue
                task.completed = True  # temporarily hide it so it doesn't block its own new slot
                slot = scheduler.next_available_slot(task.duration_minutes, day=day, day_start=p.time)
                task.completed = False
                if slot is None:
                    slot = scheduler.next_available_slot(task.duration_minutes, day=day)
                if slot and slot != task.time:
                    log(rounds, "replan", f"Moved '{p.description}' from {task.time} to {slot} (next free slot).")
                    task.time = p.time = slot
                    moved += 1
            if moved == 0:
                unresolved = problems
                log(rounds, "check", "Could not resolve the remaining problems automatically; flagging for human review.")
                break
        else:
            scheduler = Scheduler(scratch)
            unresolved = scheduler.find_conflicts() + find_overlaps(scratch, day)
            if unresolved:
                log(rounds, "check", "Still conflicting after the maximum number of rounds; flagging for human review.")
            else:
                log(rounds, "check", "Re-checked after the last move: no conflicts or overlaps.")

        # ---- final self-review against retrieved guidance
        for p in proposals:
            review = self.advisor.review_task(scratch_pet, placed[id(p)])
            if review.status == "warn":
                unresolved.append(f"{p.description}: " + " ".join(review.messages))
        log(rounds, "done", f"{len(proposals)} proposal(s) ready for approval; "
                            f"{'needs human review' if unresolved else 'no open issues'}.")
        return AgentResult(pet.name, proposals, trace, unresolved, rounds)

    @staticmethod
    def apply(pet: Pet, result: AgentResult, approved: Optional[List[int]] = None) -> List[str]:
        """Add approved proposals to the REAL pet (human-in-the-loop). `approved` is a list of indexes, or None for all."""
        added = []
        for index, proposal in enumerate(result.proposals):
            if approved is not None and index not in approved:
                continue
            pet.add_task(proposal.to_task())
            added.append(proposal.description)
        logger.info("agent apply pet=%s added=%s", pet.name, added)
        return added


def format_trace(result: AgentResult) -> str:
    """Return the trace as readable text."""
    lines = [f"Agent trace for {result.pet_name}:"]
    for step in result.trace:
        lines.append(f"  {step['step']:>2}. [{step['phase'].upper():<6}] (round {step['round']}) {step['detail']}")
    lines.append(f"  Confidence: {result.confidence:.2f} | Needs review: {result.needs_review}")
    return "\n".join(lines)


def trace_to_json(result: AgentResult) -> str:
    """Return the trace and proposals as JSON (for logs and ai_interactions.md)."""
    return json.dumps(
        {
            "pet": result.pet_name,
            "rounds": result.rounds,
            "confidence": result.confidence,
            "unresolved": result.unresolved,
            "proposals": [
                {"description": p.description, "time": p.time, "minutes": p.duration_minutes, "priority": p.priority}
                for p in result.proposals
            ],
            "trace": result.trace,
        },
        indent=2,
    )
