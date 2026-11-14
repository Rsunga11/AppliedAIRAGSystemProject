"""PawPal+ logic layer: Task, Pet, Owner and Scheduler."""

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Tuple

PRIORITIES = ("low", "medium", "high")
FREQUENCIES = ("once", "daily", "weekly")
# Animals a pet can be. The advisor only has care notes for some of them (see advisor.COVERED_SPECIES).
SPECIES = ("dog", "cat", "rabbit", "hamster", "guinea pig", "bird", "fish", "snake", "lizard", "turtle", "other")
SPECIES_ICONS = {
    "dog": "🐶", "cat": "🐱", "rabbit": "🐰", "hamster": "🐹", "guinea pig": "🐹", "bird": "🐦",
    "fish": "🐟", "snake": "🐍", "lizard": "🦎", "turtle": "🐢", "other": "🐾",
}
FREQUENCY_DAYS = {"daily": 1, "weekly": 7}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
PRIORITY_ICONS = {"high": "🔴", "medium": "🟡", "low": "🟢"}
TASK_ICONS = (  # first keyword found in the description wins
    (("walk", "run"), "🦮"),
    (("feed", "breakfast", "dinner", "lunch", "meal"), "🍽️"),
    (("med", "pill", "flea"), "💊"),
    (("play", "toy", "enrich"), "🎾"),
    (("groom", "bath", "brush"), "🛁"),
    (("vet", "appointment"), "🏥"),
)


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

    def to_dict(self) -> dict:
        """Convert to plain JSON-friendly data."""
        return {
            "description": self.description,
            "time": self.time,
            "duration_minutes": self.duration_minutes,
            "priority": self.priority,
            "frequency": self.frequency,
            "due_date": self.due_date.isoformat(),
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Rebuild a Task from to_dict() output."""
        data = dict(data)
        data["due_date"] = date.fromisoformat(data["due_date"])
        return cls(**data)

    def is_open_on(self, day: date) -> bool:
        """True if this task is due on `day` and not yet done (the only tasks that can clash)."""
        return self.due_date == day and not self.completed

    def minute_range(self) -> Tuple[int, int]:
        """Return (start, end) in minutes after midnight."""
        start = to_minutes(self.time)
        return start, start + self.duration_minutes

    def overlaps(self, other: "Task") -> bool:
        """True if the two tasks' time ranges overlap (uses ranges_overlap)."""
        return ranges_overlap(*self.minute_range(), *other.minute_range())

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

    def to_dict(self) -> dict:
        """Convert to plain JSON-friendly data."""
        return {"name": self.name, "species": self.species, "tasks": [t.to_dict() for t in self.tasks]}

    @classmethod
    def from_dict(cls, data: dict) -> "Pet":
        """Rebuild a Pet (and its tasks) from to_dict() output."""
        return cls(data["name"], data.get("species", "dog"), [Task.from_dict(t) for t in data.get("tasks", [])])


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

    def to_dict(self) -> dict:
        """Convert to plain JSON-friendly data."""
        return {"name": self.name, "pets": [p.to_dict() for p in self.pets]}

    @classmethod
    def from_dict(cls, data: dict) -> "Owner":
        """Rebuild an Owner (with pets and tasks) from to_dict() output."""
        return cls(data["name"], [Pet.from_dict(p) for p in data.get("pets", [])])

    def save_to_json(self, path: str = "data.json") -> None:
        """Write the owner, pets and tasks to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_json(cls, path: str = "data.json") -> "Owner":
        """Load an owner from a JSON file; raises FileNotFoundError if it doesn't exist."""
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


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

    def sort_by_priority_then_time(self, tasks: Optional[List[Task]] = None) -> List[Task]:
        """Sort high -> low priority first, then by due date and time inside each priority."""
        if tasks is None:
            tasks = self.get_all_tasks()
        return sorted(tasks, key=lambda t: (PRIORITY_RANK[t.priority], t.due_date, t.time))

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

    def next_available_slot(
        self,
        duration: int,
        day: Optional[date] = None,
        day_start: str = "07:00",
        day_end: str = "21:00",
        step: int = 15,
    ) -> Optional[str]:
        """Return the earliest "HH:MM" where `duration` minutes fit between open tasks that day, or None."""
        day = day or date.today()
        busy = [t.minute_range() for t in self.get_all_tasks() if t.is_open_on(day)]
        start, window_end = to_minutes(day_start), to_minutes(day_end)
        while start + duration <= window_end:
            end = start + duration
            if not any(ranges_overlap(start, end, b_start, b_end) for b_start, b_end in busy):
                return to_hhmm(start)
            start += step
        return None

    def format_schedule(self, tasks: List[Task]) -> str:
        """Return a readable text table with status and priority icons."""
        if not tasks:
            return "(no tasks)"
        lines = [f"{'':2} {'Date':<5} {'Time':<6} {'Task':<22} {'Pet':<9} {'Min':>4}  Priority"]
        for task in tasks:
            pet = self.pet_for(task)
            status = "✅" if task.completed else "⏳"
            icon = task_icon(task.description)
            label = f"{icon} {task.description}"
            lines.append(
                f"{status} {task.due_date:%m-%d} {task.time:<6} {label:<22} {pet.name if pet else '?':<9} "
                f"{task.duration_minutes:>4}  {PRIORITY_ICONS[task.priority]} {task.priority}"
            )
        return "\n".join(lines)


def species_icon(species: str) -> str:
    """Emoji for an animal type (a paw print if we don't know it)."""
    return SPECIES_ICONS.get(species, "🐾")


def task_icon(description: str) -> str:
    """Pick an emoji for a task from keywords in its description."""
    text = description.lower()
    for keywords, icon in TASK_ICONS:
        if any(k in text for k in keywords):
            return icon
    return "🐾"


def ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    """The ONE definition of overlap: each range starts before the other ends.

    Back-to-back ranges (one ends exactly when the next starts) do not overlap.
    """
    return start_a < end_b and start_b < end_a


def to_minutes(hhmm: str) -> int:
    """Convert "HH:MM" to minutes after midnight."""
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def to_hhmm(total_minutes: int) -> str:
    """Convert minutes after midnight back to a zero-padded "HH:MM"."""
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
