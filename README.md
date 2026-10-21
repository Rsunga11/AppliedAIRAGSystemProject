# PawPal+ (Module 2 Project)

PawPal+ is a Streamlit app that helps a busy pet owner plan care tasks (walks, feeding, meds, play, grooming) for one or more pets. The logic lives in a separate Python module (`pawpal_system.py`) so it can be tested from the command line before the UI uses it.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

## ✨ Features

- **Multiple pets, one owner:** an `Owner` holds several `Pet`s, and the `Scheduler` reads every pet's tasks through `Owner.get_all_tasks()`.
- **Sorting by time** (`Scheduler.sort_by_time`) and **by priority, then time** (`Scheduler.sort_by_priority_then_time`).
- **Filtering** by pet name and/or completion status (`Scheduler.filter_tasks`).
- **Conflict warnings** when two open tasks share the same date and time (`Scheduler.find_conflicts`), shown as a warning in the UI.
- **Recurring tasks:** completing a daily or weekly task creates the next one automatically (`Scheduler.mark_task_complete`).
- **Next free slot finder** that respects task durations (`Scheduler.next_available_slot`).
- **Saved data:** pets and tasks are written to `data.json` and loaded again on the next run (`Owner.save_to_json` / `Owner.load_from_json`).
- **Readable output:** emoji status/priority/task-type icons in the CLI table and the Streamlit table.
- **Input validation:** a bad time (`"8am"`), priority or frequency raises a clear `ValueError` when the `Task` is created.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```bash
python main.py            # CLI demo of the logic layer
streamlit run app.py      # the web app
python -m pytest          # run the tests
```

## 🛠️ Implementation Summary

The logic is in `pawpal_system.py`:

- `Task` (dataclass): one activity with a description, `"HH:MM"` time, duration, priority, frequency (`once`/`daily`/`weekly`), due date and completion flag. It validates its inputs and can create its own next occurrence.
- `Pet` (dataclass): a name, species and its own list of tasks.
- `Owner` (dataclass): owns the pets, returns every task with `get_all_tasks()`, and saves/loads everything as JSON.
- `Scheduler`: takes an `Owner` and does the organizing: sorting, filtering, conflict detection, recurrence, free-slot search and text formatting.

`main.py` is the CLI demo I used to check the logic before wiring up `app.py`. In the UI the `Owner` is stored in `st.session_state` so it isn't recreated on every Streamlit rerun.

## 🖥️ Sample Output

Output of `python main.py`:

```
== Today's Schedule (sorted by time) ==
   Date  Time   Task                   Pet        Min  Priority
⏳ 10-21 07:30  🦮 Morning walk         Biscuit     30  🔴 high
⏳ 10-21 07:30  💊 Flea medicine        Mochi        5  🔴 high
⏳ 10-21 08:00  🍽️ Breakfast           Mochi       10  🔴 high
⏳ 10-21 12:00  🎾 Play session         Mochi       20  🟢 low
⏳ 10-21 18:00  🦮 Evening walk         Biscuit     30  🟡 medium

== Conflict check ==
WARNING: Conflict on 2026-10-21 at 07:30: Morning walk (Biscuit), Flea medicine (Mochi)

== Only Mochi's tasks ==
   Date  Time   Task                   Pet        Min  Priority
⏳ 10-21 07:30  💊 Flea medicine        Mochi        5  🔴 high
⏳ 10-21 08:00  🍽️ Breakfast           Mochi       10  🔴 high
⏳ 10-21 12:00  🎾 Play session         Mochi       20  🟢 low

== Priority first, then time ==
   Date  Time   Task                   Pet        Min  Priority
⏳ 10-21 07:30  🦮 Morning walk         Biscuit     30  🔴 high
⏳ 10-21 07:30  💊 Flea medicine        Mochi        5  🔴 high
⏳ 10-21 08:00  🍽️ Breakfast           Mochi       10  🔴 high
⏳ 10-21 18:00  🦮 Evening walk         Biscuit     30  🟡 medium
⏳ 10-21 12:00  🎾 Play session         Mochi       20  🟢 low

== Next free 45-minute slot today ==
08:15

== Recurring task: complete the morning walk ==
'Morning walk' done -> next one is due 2026-10-22
   Date  Time   Task                   Pet        Min  Priority
✅ 10-21 07:30  🦮 Morning walk         Biscuit     30  🔴 high
⏳ 10-21 18:00  🦮 Evening walk         Biscuit     30  🟡 medium
⏳ 10-22 07:30  🦮 Morning walk         Biscuit     30  🔴 high

== Persistence: save to JSON and load it back ==
Reloaded owner matches original: True
```

## 🧪 Testing PawPal+

```bash
python -m pytest
```

The 23 tests cover:

- **Basics:** `mark_complete()` changes status, adding a task grows a pet's task count, and `Owner.get_all_tasks()` collects tasks from every pet.
- **Sorting:** tasks added out of order come back chronologically, and today's schedule ignores other days.
- **Filtering:** by pet (case-insensitive), by completion status, and both together.
- **Recurrence:** daily creates a task for the next day, weekly for +7 days, and a one-time task creates nothing.
- **Conflicts:** same-time tasks (same pet or different pets) are flagged, while different times, different days and completed tasks are not.
- **Edge cases:** a pet with no tasks, invalid times and priorities, priority sorting, next free slot (including a day with nothing scheduled and a task longer than the day), and a JSON save/load round trip.

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.7.0 -- C:\Users\rsung\AI110\Pawpal\ai110-module2show-pawpal-starter\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\rsung\AI110\Pawpal\ai110-module2show-pawpal-starter
plugins: anyio-4.15.1
collecting ... collected 23 items

tests/test_pawpal.py::test_mark_complete_changes_status PASSED           [  4%]
tests/test_pawpal.py::test_adding_task_increases_pet_task_count PASSED   [  8%]
tests/test_pawpal.py::test_owner_get_all_tasks_collects_every_pet PASSED [ 13%]
tests/test_pawpal.py::test_sort_by_time_returns_chronological_order PASSED [ 17%]
tests/test_pawpal.py::test_todays_schedule_ignores_other_days PASSED     [ 21%]
tests/test_pawpal.py::test_pet_with_no_tasks_gives_empty_schedule PASSED [ 26%]
tests/test_pawpal.py::test_filter_by_pet_and_completion PASSED           [ 30%]
tests/test_pawpal.py::test_completing_daily_task_creates_task_for_next_day PASSED [ 34%]
tests/test_pawpal.py::test_completing_weekly_task_creates_task_seven_days_later PASSED [ 39%]
tests/test_pawpal.py::test_one_time_task_does_not_repeat PASSED          [ 43%]
tests/test_pawpal.py::test_conflict_detection_flags_duplicate_times PASSED [ 47%]
tests/test_pawpal.py::test_no_conflict_for_different_times_or_days PASSED [ 52%]
tests/test_pawpal.py::test_completed_tasks_do_not_conflict PASSED        [ 56%]
tests/test_pawpal.py::test_bad_time_is_rejected[8am] PASSED              [ 60%]
tests/test_pawpal.py::test_bad_time_is_rejected[25:00] PASSED            [ 65%]
tests/test_pawpal.py::test_bad_time_is_rejected[07:61] PASSED            [ 69%]
tests/test_pawpal.py::test_bad_time_is_rejected[] PASSED                 [ 73%]
tests/test_pawpal.py::test_bad_priority_is_rejected PASSED               [ 78%]
tests/test_pawpal.py::test_sort_by_priority_then_time PASSED             [ 82%]
tests/test_pawpal.py::test_next_available_slot_skips_busy_blocks PASSED  [ 86%]
tests/test_pawpal.py::test_next_available_slot_on_empty_day_is_day_start PASSED [ 91%]
tests/test_pawpal.py::test_json_round_trip PASSED                        [ 95%]
tests/test_pawpal.py::test_load_missing_file_raises PASSED               [100%]

============================= 23 passed in 0.06s ==============================
```

**Confidence level: ⭐⭐⭐⭐☆ (4/5).** The scheduling behaviors I built are all covered and pass. I held back one star because conflict detection only compares exact start times, not overlapping durations, and the Streamlit UI was only checked with Streamlit's `AppTest` harness and a manual run, not automated browser tests.

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Sorting by time | `Scheduler.sort_by_time()` | Sorts by due date, then the `"HH:MM"` string, which sorts correctly as text because times are zero-padded. |
| Sorting by priority | `Scheduler.sort_by_priority_then_time()` | High, then medium, then low; ties broken by date and time. |
| Filtering | `Scheduler.filter_tasks(pet_name=, completed=)` | Filter by pet, completion status, or both. |
| Conflict handling | `Scheduler.find_conflicts()` | Returns warning strings for open tasks sharing a date and time (same or different pets). Never raises. |
| Recurring tasks | `Task.next_occurrence()`, `Scheduler.mark_task_complete()` | Daily: due date + 1 day; weekly: + 7 days, using `timedelta`. |
| Free slot search | `Scheduler.next_available_slot(duration, day)` | Earliest start on a 15-minute grid between 07:00 and 21:00 where the block overlaps no open task. |

### Priority scheduling example (Challenge 3)

From the demo output above, `sort_by_priority_then_time()` puts all `high` tasks first (in time order), then `medium`, then `low`: the 12:00 play session (low) comes after the 18:00 evening walk (medium) even though it is earlier in the day.

### Data persistence (Challenge 2)

- `Task`, `Pet` and `Owner` each have `to_dict()`/`from_dict()` that convert to plain JSON-friendly data (dates become ISO strings).
- `Owner.save_to_json(path="data.json")` writes everything; `Owner.load_from_json(path)` reads it back.
- `app.py` loads `data.json` the first time the page runs (if the file exists) and saves after each change. `data.json` is in `.gitignore`.
- Files changed: `pawpal_system.py`, `app.py`, `.gitignore`, `tests/test_pawpal.py` (round-trip test). I used a custom dictionary conversion instead of a library like marshmallow, since there are only three small classes.

### Output formatting (Challenge 4)

`Scheduler.format_schedule()` builds a text table with ⏳/✅ status, 🔴🟡🟢 priority icons and a task-type emoji picked by `task_icon()` from keywords in the description (🦮 walk, 🍽️ meal, 💊 medicine, 🎾 play, 🛁 grooming, 🏥 vet). The Streamlit table in `app.py` reuses `task_icon` and `PRIORITY_ICONS`. No extra libraries were needed.

## 📸 Demo Walkthrough

1. Open the app with `streamlit run app.py`. Enter an owner name and add a pet (for example Biscuit, a dog). A second pet, Mochi the cat, can be added the same way. Duplicate or blank pet names show an error.
2. Under "Schedule a task", choose a pet, description, date, time, duration, priority and how often it repeats (once, daily, weekly) and click "Add task". Each task is saved to `data.json`.
3. Add two tasks at the same time (for example a walk and a flea medicine at 07:30). A yellow warning appears naming both tasks and suggesting the next free slot.
4. In "Your schedule", the table is sorted by time by default. Use the dropdowns to filter by pet or by To do/Done, or switch to "Priority, then time".
5. Pick a task under "Mark a task done" and click "Mark complete". If it repeats, the app confirms a new task was added for the next day or week.
6. Use "Find a free slot" to ask for the earliest free block of N minutes on a chosen day.
7. Stop and restart the app: the pets and tasks are still there because they were loaded from `data.json`.

The CLI version of the same behaviors is in the "Sample Output" section above.
