"""PawPal+ logic layer (skeleton drafted from the UML in diagrams/uml.mmd)."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Task:
    description: str
    time: str  # "HH:MM"
    frequency: str = "once"
    completed: bool = False

    def mark_complete(self) -> None:
        pass


@dataclass
class Pet:
    name: str
    species: str
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        pass


@dataclass
class Owner:
    name: str
    pets: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        pass

    def get_all_tasks(self) -> List[Task]:
        pass


class Scheduler:
    def __init__(self, owner: Owner):
        self.owner = owner

    def get_todays_schedule(self) -> List[Task]:
        pass

    def sort_by_time(self) -> List[Task]:
        pass
