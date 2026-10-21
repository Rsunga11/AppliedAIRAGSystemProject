"""PawPal+ logic layer: Task, Pet, Owner and Scheduler."""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

PRIORITIES = ("low", "medium", "high")
FREQUENCIES = ("once", "daily", "weekly")


@dataclass
class Task:
    """One pet care activity (a walk, a feeding, a medication, ...)."""

    description: str
    time: str  # 24-hour "HH:MM"
    duration_minutes: int = 15
    priority: str = "medium"
    frequency: str = "once"
    due_date: date = field(default_factory=date.today)
    completed: bool = False

    def mark_complete(self) -> None:
        """Mark this task as done."""
        self.completed = True


@dataclass
class Pet:
    """A pet and the care tasks that belong to it."""

    name: str
    species: str = "dog"
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet."""
        self.tasks.append(task)


@dataclass
class Owner:
    """A pet owner who manages one or more pets."""

    name: str
    pets: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        self.pets.append(pet)

    def get_all_tasks(self) -> List[Task]:
        """Return every task from every pet in one list."""
        return [task for pet in self.pets for task in pet.tasks]


class Scheduler:
    """The 'brain': reads tasks through the Owner and organizes them."""

    def __init__(self, owner: Owner):
        self.owner = owner

    def get_todays_schedule(self, today: Optional[date] = None) -> List[Task]:
        """Return today's tasks sorted by time."""
        today = today or date.today()
        todays = [t for t in self.owner.get_all_tasks() if t.due_date == today]
        return sorted(todays, key=lambda t: t.time)
