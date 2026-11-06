"""CLI demo for the PawPal+ logic layer (run: python main.py)."""

import os
import sys
import tempfile

from advisor import CareAdvisor, configure_logging
from agent import CarePlanAgent, describe_overlap, format_trace, overlap_pairs
from llm import from_env
from pawpal_system import Owner, Pet, Scheduler, Task
from retriever import KnowledgeBase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # so emoji print on Windows terminals


def section(title: str) -> None:
    """Print a heading line."""
    print(f"\n== {title} ==")


def ai_demo(owner: Owner, biscuit: Pet) -> None:
    """Show the Care Advisor (RAG), its guardrails, and the plan/act/check agent."""
    configure_logging()
    llm = from_env()
    advisor = CareAdvisor(KnowledgeBase(), llm=llm)
    print("\n\n######## AI Care Advisor ########")
    print(f"Mode: {'Gemini + retrieval' if llm else 'offline retrieval (no GEMINI_API_KEY set)'}")

    section("RAG: questions answered from the knowledge base")
    for question, species in [
        ("How long should I walk my dog?", "dog"),
        ("How often should I feed my cat?", "cat"),
        ("Why is the sky blue?", None),
    ]:
        answer = advisor.answer_question(question, species)
        print(f"Q: {question}")
        print(f"A: {answer.text}")
        print(f"   confidence={answer.confidence:.2f} needs_review={answer.needs_review} sources={answer.sources or 'none'}\n")

    section("Guardrails")
    for question in ["How much ibuprofen can I give my dog?", "", "walk " * 200]:
        answer = advisor.answer_question(question, "dog")
        shown = question if len(question) < 60 else question[:30] + "...(long)"
        print(f"Q: {shown!r}\n   refused={answer.refused}: {answer.text}\n")

    section("RAG-backed review of a task")
    quick = Task("Quick walk", "09:00", 5, "medium")
    review = advisor.review_task(biscuit, quick)
    print(f"'Quick walk' (5 min) for a dog -> {review.status.upper()} (confidence {review.confidence:.2f})")
    print("   " + " ".join(review.messages))
    print(f"   source: {review.sources}")

    section("Agent: plan -> act -> check -> re-plan (proposals only)")
    agent = CarePlanAgent(advisor)
    fresh = Pet("Rex", "dog")
    owner.add_pet(fresh)
    fresh.add_task(Task("Vet call", "07:30", 20, "high"))  # already blocks the morning routine slot
    result = agent.run(owner, fresh)
    print(format_trace(result))
    print(f"\nTasks on Rex BEFORE approval: {len(fresh.tasks)} (only the existing 'Vet call'; the agent never edits data on its own)")

    section("Human approval: approve the first 3 proposals")
    existing_ids = {id(t) for t in fresh.tasks}
    added = agent.apply(fresh, result, approved=[0, 1, 2])
    print("Added:", added)
    print(Scheduler(owner).format_schedule(Scheduler(owner).sort_by_time(fresh.tasks)))
    new_ids = {id(t) for t in fresh.tasks} - existing_ids
    new_overlaps = [
        describe_overlap(pair)
        for pair in overlap_pairs(owner, fresh.tasks[0].due_date)
        if id(pair[1]) in new_ids or id(pair[3]) in new_ids
    ]
    print("Overlaps involving the newly added tasks:", new_overlaps or "none")


def main() -> None:
    owner = Owner("Jordan")
    biscuit = Pet("Biscuit", "dog")
    mochi = Pet("Mochi", "cat")
    owner.add_pet(biscuit)
    owner.add_pet(mochi)
    scheduler = Scheduler(owner)

    # Added out of order on purpose so sorting has something to do.
    biscuit.add_task(Task("Evening walk", "18:00", 30, "medium", "daily"))
    mochi.add_task(Task("Breakfast", "08:00", 10, "high", "daily"))
    biscuit.add_task(Task("Morning walk", "07:30", 30, "high", "daily"))
    mochi.add_task(Task("Flea medicine", "07:30", 5, "high", "weekly"))  # same time as the walk
    mochi.add_task(Task("Play session", "12:00", 20, "low"))

    section("Today's Schedule (sorted by time)")
    print(scheduler.format_schedule(scheduler.get_todays_schedule()))

    section("Conflict check")
    for warning in scheduler.find_conflicts() or ["No conflicts."]:
        print("WARNING:", warning)

    section("Only Mochi's tasks")
    print(scheduler.format_schedule(scheduler.sort_by_time(scheduler.filter_tasks(pet_name="Mochi"))))

    section("Priority first, then time")
    print(scheduler.format_schedule(scheduler.sort_by_priority_then_time()))

    section("Next free 45-minute slot today")
    print(scheduler.next_available_slot(45))

    section("Recurring task: complete the morning walk")
    walk = next(t for t in biscuit.tasks if t.description == "Morning walk")
    follow_up = scheduler.mark_task_complete(walk)
    print(f"'{walk.description}' done -> next one is due {follow_up.due_date}")
    print(scheduler.format_schedule(scheduler.sort_by_time(scheduler.filter_tasks(pet_name="Biscuit"))))

    section("Persistence: save to JSON and load it back")
    path = os.path.join(tempfile.gettempdir(), "pawpal_demo.json")
    owner.save_to_json(path)
    print("Reloaded owner matches original:", Owner.load_from_json(path) == owner)
    os.remove(path)

    if "--no-ai" not in sys.argv:
        ai_demo(owner, biscuit)


if __name__ == "__main__":
    main()
