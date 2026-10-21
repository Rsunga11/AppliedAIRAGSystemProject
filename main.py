"""CLI demo for the PawPal+ logic layer (run: python main.py)."""

import os
import sys
import tempfile

from pawpal_system import Owner, Pet, Scheduler, Task

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # so emoji print on Windows terminals


def section(title: str) -> None:
    """Print a heading line."""
    print(f"\n== {title} ==")


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


if __name__ == "__main__":
    main()
