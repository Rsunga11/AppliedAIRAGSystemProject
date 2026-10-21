"""PawPal+ logic layer: Task, Pet, Owner and Scheduler."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

PRIORITIES = ("low", "medium", "high")
FREQUENCIES = ("once", "daily", "weekly")
FREQUENCY_DAYS = {"daily": 1, "weekly": 7}


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

    def __post_init__(self) -> None:
        """Reject a bad time, priority or frequency as early as possible."""
        try:
            hours, minutes = self.time.split(":")
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                raise ValueError
        except ValueError:
            raise ValueError(f"time must look like HH:MM (24-hour), got {self.time!r}")
        if self.priority not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}, got {self.priority!r}")
        if self.frequency not in FREQUENCIES:
            raise ValueError(f"frequency must be one of {FREQUENCIES}, got {self.frequency!r}")

    def mark_complete(self) -> None:
        """Mark this task as done."""
        self.completed = True

    def next_occurrence(self) -> Optional["Task"]:
        """Return a fresh copy due on the next day/week, or None if it doesn't repeat."""
        days = FREQUENCY_DAYS.get(self.frequency)
        if days is None:
            return None
        return Task(
            description=self.description,
            time=self.time,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            frequency=self.frequency,
            due_date=self.due_date + timedelta(days=days),
        )


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

    def get_all_tasks(self) -> List[Task]:
        """Return every task across all of the owner's pets."""
        return self.owner.get_all_tasks()

    def get_todays_schedule(self, today: Optional[date] = None) -> List[Task]:
        """Return today's tasks sorted by time."""
        today = today or date.today()
        todays = [t for t in self.get_all_tasks() if t.due_date == today]
        return self.sort_by_time(todays)

    def sort_by_time(self, tasks: Optional[List[Task]] = None) -> List[Task]:
        """Sort tasks by due date, then by time; "HH:MM" strings sort correctly as text."""
        if tasks is None:
            tasks = self.get_all_tasks()
        return sorted(tasks, key=lambda t: (t.due_date, t.time))

    def filter_tasks(
        self,
        pet_name: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> List[Task]:
        """Return tasks for one pet and/or with a given completion status (None means any)."""
        result = []
        for pet in self.owner.pets:
            if pet_name is not None and pet.name.lower() != pet_name.lower():
                continue
            for task in pet.tasks:
                if completed is not None and task.completed != completed:
                    continue
                result.append(task)
        return result

    def pet_for(self, task: Task) -> Optional[Pet]:
        """Return the pet that owns this task, or None."""
        for pet in self.owner.pets:
            if any(t is task for t in pet.tasks):
                return pet
        return None

    def mark_task_complete(self, task: Task) -> Optional[Task]:
        """Complete a task; if it repeats, add the next one to the same pet and return it."""
        task.mark_complete()
        pet = self.pet_for(task)
        follow_up = task.next_occurrence()
        if follow_up is not None and pet is not None:
            pet.add_task(follow_up)
        return follow_up

    def find_conflicts(self) -> List[str]:
        """Return warning messages for open tasks that share a date and time (never raises)."""
        slots = {}
        for pet in self.owner.pets:
            for task in pet.tasks:
                if not task.completed:
                    slots.setdefault((task.due_date, task.time), []).append((pet, task))
        warnings = []
        for (day, time), entries in sorted(slots.items()):
            if len(entries) > 1:
                names = ", ".join(f"{t.description} ({p.name})" for p, t in entries)
                warnings.append(f"Conflict on {day} at {time}: {names}")
        return warnings
