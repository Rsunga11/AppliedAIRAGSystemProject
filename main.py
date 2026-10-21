"""CLI demo for the PawPal+ logic layer (run: python main.py)."""

from pawpal_system import Owner, Pet, Scheduler, Task


def print_schedule(owner: Owner, scheduler: Scheduler) -> None:
    """Print today's schedule in a readable format."""
    print(f"Today's Schedule for {owner.name}")
    print("-" * 44)
    for task in scheduler.get_todays_schedule():
        pet_name = next(p.name for p in owner.pets if task in p.tasks)
        print(f"{task.time}  {task.description:<18} {pet_name:<8} ({task.duration_minutes} min)")


def main() -> None:
    owner = Owner("Jordan")
    biscuit = Pet("Biscuit", "dog")
    mochi = Pet("Mochi", "cat")
    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    biscuit.add_task(Task("Morning walk", "07:30", 30, "high"))
    mochi.add_task(Task("Breakfast", "08:00", 10, "high"))
    biscuit.add_task(Task("Evening walk", "18:00", 30, "medium"))

    print_schedule(owner, Scheduler(owner))


if __name__ == "__main__":
    main()
