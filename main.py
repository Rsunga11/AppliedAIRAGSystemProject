"""CLI demo for the PawPal+ logic layer (run: python main.py)."""

import sys
from datetime import date

from pawpal_system import Owner, Pet, Scheduler, Task


def print_schedule(title: str, scheduler: Scheduler, tasks) -> None:
    """Print a list of tasks in a readable format."""
    print(title)
    print("-" * 52)
    for task in tasks:
        pet = scheduler.pet_for(task)
        status = "done" if task.completed else "todo"
        print(f"{task.due_date} {task.time}  {task.description:<16} {pet.name:<8} [{task.priority}] {status}")
    print()


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

    print_schedule("Today's Schedule (sorted by time)", scheduler, scheduler.get_todays_schedule())

    print("Conflict check")
    print("-" * 52)
    for warning in scheduler.find_conflicts() or ["No conflicts."]:
        print("WARNING:", warning)
    print()

    print_schedule("Only Mochi's tasks", scheduler, scheduler.sort_by_time(scheduler.filter_tasks(pet_name="Mochi")))

    walk = next(t for t in biscuit.tasks if t.description == "Morning walk")
    follow_up = scheduler.mark_task_complete(walk)
    print(f"Marked '{walk.description}' complete -> next one is due {follow_up.due_date}")
    print()
    print_schedule("Pending tasks (completed=False)", scheduler, scheduler.sort_by_time(scheduler.filter_tasks(completed=False)))


if __name__ == "__main__":
    main()
