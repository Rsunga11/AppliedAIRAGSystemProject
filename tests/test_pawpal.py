from datetime import date, timedelta

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task

TODAY = date(2026, 10, 21)


def make_owner():
    owner = Owner("Jordan")
    dog = Pet("Biscuit", "dog")
    cat = Pet("Mochi", "cat")
    owner.add_pet(dog)
    owner.add_pet(cat)
    return owner, dog, cat


# ---- basics -----------------------------------------------------------------

def test_mark_complete_changes_status():
    task = Task("Feed", "08:00")
    assert task.completed is False
    task.mark_complete()
    assert task.completed is True


def test_adding_task_increases_pet_task_count():
    pet = Pet("Biscuit", "dog")
    assert len(pet.tasks) == 0
    pet.add_task(Task("Walk", "07:30"))
    assert len(pet.tasks) == 1


def test_owner_get_all_tasks_collects_every_pet():
    owner, dog, cat = make_owner()
    dog.add_task(Task("Walk", "07:30"))
    cat.add_task(Task("Feed", "08:00"))
    assert len(owner.get_all_tasks()) == 2


# ---- sorting ----------------------------------------------------------------

def test_sort_by_time_returns_chronological_order():
    owner, dog, cat = make_owner()
    dog.add_task(Task("Evening walk", "18:00", due_date=TODAY))
    cat.add_task(Task("Breakfast", "08:00", due_date=TODAY))
    dog.add_task(Task("Morning walk", "07:30", due_date=TODAY))
    times = [t.time for t in Scheduler(owner).sort_by_time()]
    assert times == ["07:30", "08:00", "18:00"]


def test_todays_schedule_ignores_other_days():
    owner, dog, _ = make_owner()
    dog.add_task(Task("Today", "09:00", due_date=TODAY))
    dog.add_task(Task("Tomorrow", "07:00", due_date=TODAY + timedelta(days=1)))
    schedule = Scheduler(owner).get_todays_schedule(today=TODAY)
    assert [t.description for t in schedule] == ["Today"]


def test_pet_with_no_tasks_gives_empty_schedule():
    owner, _, _ = make_owner()
    scheduler = Scheduler(owner)
    assert scheduler.get_todays_schedule(today=TODAY) == []
    assert scheduler.find_conflicts() == []


# ---- filtering --------------------------------------------------------------

def test_filter_by_pet_and_completion():
    owner, dog, cat = make_owner()
    walk = Task("Walk", "07:30")
    feed = Task("Feed", "08:00")
    dog.add_task(walk)
    cat.add_task(feed)
    feed.mark_complete()
    scheduler = Scheduler(owner)
    assert scheduler.filter_tasks(pet_name="biscuit") == [walk]
    assert scheduler.filter_tasks(completed=True) == [feed]
    assert scheduler.filter_tasks(pet_name="Mochi", completed=False) == []


# ---- recurrence -------------------------------------------------------------

def test_completing_daily_task_creates_task_for_next_day():
    owner, dog, _ = make_owner()
    task = Task("Walk", "07:30", frequency="daily", due_date=TODAY)
    dog.add_task(task)
    follow_up = Scheduler(owner).mark_task_complete(task)
    assert task.completed is True
    assert follow_up.due_date == TODAY + timedelta(days=1)
    assert follow_up.completed is False
    assert follow_up in dog.tasks and len(dog.tasks) == 2


def test_completing_weekly_task_creates_task_seven_days_later():
    owner, dog, _ = make_owner()
    task = Task("Bath", "10:00", frequency="weekly", due_date=TODAY)
    dog.add_task(task)
    follow_up = Scheduler(owner).mark_task_complete(task)
    assert follow_up.due_date == TODAY + timedelta(days=7)


def test_one_time_task_does_not_repeat():
    owner, dog, _ = make_owner()
    task = Task("Vet visit", "15:00", frequency="once")
    dog.add_task(task)
    assert Scheduler(owner).mark_task_complete(task) is None
    assert len(dog.tasks) == 1


# ---- conflicts --------------------------------------------------------------

def test_conflict_detection_flags_duplicate_times():
    owner, dog, cat = make_owner()
    dog.add_task(Task("Walk", "07:30", due_date=TODAY))
    cat.add_task(Task("Medicine", "07:30", due_date=TODAY))
    warnings = Scheduler(owner).find_conflicts()
    assert len(warnings) == 1
    assert "07:30" in warnings[0] and "Walk" in warnings[0] and "Medicine" in warnings[0]


def test_no_conflict_for_different_times_or_days():
    owner, dog, _ = make_owner()
    dog.add_task(Task("Walk", "07:30", due_date=TODAY))
    dog.add_task(Task("Feed", "08:00", due_date=TODAY))
    dog.add_task(Task("Walk again", "07:30", due_date=TODAY + timedelta(days=1)))
    assert Scheduler(owner).find_conflicts() == []


def test_completed_tasks_do_not_conflict():
    owner, dog, cat = make_owner()
    done = Task("Walk", "07:30", due_date=TODAY)
    dog.add_task(done)
    cat.add_task(Task("Medicine", "07:30", due_date=TODAY))
    done.mark_complete()
    assert Scheduler(owner).find_conflicts() == []


# ---- validation -------------------------------------------------------------

@pytest.mark.parametrize("bad_time", ["8am", "25:00", "07:61", ""])
def test_bad_time_is_rejected(bad_time):
    with pytest.raises(ValueError):
        Task("Walk", bad_time)


def test_bad_priority_is_rejected():
    with pytest.raises(ValueError):
        Task("Walk", "07:30", priority="urgent")


# ---- extras: priority, next slot, persistence --------------------------------

def test_sort_by_priority_then_time():
    owner, dog, cat = make_owner()
    dog.add_task(Task("Low early", "06:00", priority="low", due_date=TODAY))
    dog.add_task(Task("High late", "20:00", priority="high", due_date=TODAY))
    cat.add_task(Task("High early", "08:00", priority="high", due_date=TODAY))
    names = [t.description for t in Scheduler(owner).sort_by_priority_then_time()]
    assert names == ["High early", "High late", "Low early"]


def test_next_available_slot_skips_busy_blocks():
    owner, dog, _ = make_owner()
    dog.add_task(Task("Walk", "07:30", 30, due_date=TODAY))
    dog.add_task(Task("Feed", "08:00", 10, due_date=TODAY))
    scheduler = Scheduler(owner)
    assert scheduler.next_available_slot(20, day=TODAY) == "07:00"  # fits before the walk
    assert scheduler.next_available_slot(60, day=TODAY) == "08:15"  # first gap after both tasks
    assert scheduler.next_available_slot(15 * 60, day=TODAY) is None  # longer than the whole day


def test_next_available_slot_on_empty_day_is_day_start():
    owner, _, _ = make_owner()
    assert Scheduler(owner).next_available_slot(30, day=TODAY) == "07:00"


def test_json_round_trip(tmp_path):
    owner, dog, _ = make_owner()
    dog.add_task(Task("Walk", "07:30", 30, "high", "daily", due_date=TODAY))
    path = tmp_path / "data.json"
    owner.save_to_json(str(path))
    assert Owner.load_from_json(str(path)) == owner


def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        Owner.load_from_json("does_not_exist.json")
