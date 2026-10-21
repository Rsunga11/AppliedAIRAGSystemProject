# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🛠️ Implementation Summary

The logic lives in `pawpal_system.py`. `Task` is a dataclass for one activity (description, time, duration, priority, frequency, completion). Each `Pet` keeps its own list of tasks, and an `Owner` keeps the list of pets and exposes `get_all_tasks()`, which returns every pet's tasks together. The `Scheduler` takes an `Owner` and reads tasks only through that method, so it works across all pets. `main.py` is a CLI demo that I used to check the logic before touching the Streamlit UI.

## 🖥️ Sample Output

Output of `python main.py`:

```
Today's Schedule for Jordan
--------------------------------------------
07:30  Morning walk       Biscuit  (30 min)
08:00  Breakfast          Mochi    (10 min)
18:00  Evening walk       Biscuit  (30 min)
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Sorting by time | `Scheduler.sort_by_time()` | Sorts by due date, then by the `"HH:MM"` string, which sorts correctly as plain text because times are zero-padded. |
| Filtering | `Scheduler.filter_tasks(pet_name=, completed=)` | Filter by pet name (case-insensitive), by completion status, or both. |
| Conflict handling | `Scheduler.find_conflicts()` | Returns warning strings for open tasks that share the same date and time, for the same pet or different pets. It never raises. |
| Recurring tasks | `Task.next_occurrence()`, `Scheduler.mark_task_complete()` | Completing a daily task creates a copy due tomorrow (`timedelta(days=1)`), a weekly one a copy due in 7 days. |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
