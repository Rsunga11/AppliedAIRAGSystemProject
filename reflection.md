# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

The three things I want a pet owner to be able to do are: add a pet, schedule a care task (like a walk or feeding) for that pet at a certain time, and see today's tasks in order.

My first UML had four classes. `Task` is one activity (description, time, frequency, whether it's done) and knows how to mark itself complete. `Pet` holds a pet's name and species plus its list of tasks. `Owner` holds the pets and has one method, `get_all_tasks()`, that returns every pet's tasks together. `Scheduler` is the "brain": it takes an `Owner` and reads tasks through that method so it works across all pets, not just one. I made `Task`, `Pet` and `Owner` dataclasses to keep them short, and left `Scheduler` as a normal class because it mostly holds behavior instead of data.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes. My first UML had only `description`, `time`, `frequency` and `completed` on `Task`, and `Scheduler` only had `get_todays_schedule` and `sort_by_time`. While building it I added `duration_minutes`, `priority` and `due_date` to `Task`, because the scheduler needs a date to know what "today" means and to create the next copy of a recurring task, and the app needed duration and priority. I also put the "create the next recurring task" logic in `Task.next_occurrence()` and kept `Scheduler.mark_task_complete()` responsible for adding it to the right pet, because a `Task` doesn't know which pet owns it. The final `Scheduler` also gained filtering, conflict detection, a free-slot finder and formatting, and `Owner` gained JSON save/load. The final diagram is `diagrams/uml_final.mmd`.

Reviewing the skeleton, one thing I noticed is that tasks have no link back to their pet, which makes "which pet is this task for?" a lookup. I kept it that way (`Scheduler.pet_for`) instead of storing a `pet` field on `Task`, so a task can't point at a pet that doesn't contain it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

The scheduler considers the time a task is due (date plus `HH:MM`), its duration, its priority, whether it repeats, and whether it is already done. Time matters most, because a pet owner mostly wants a day in order, so sorting by time is the default. Priority is the second view (high first, then time), which helps when the day is too full. Duration is only used when looking for a free slot. I left out owner preferences (like "no walks after 8pm") to keep the scope small.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

My conflict detection only flags tasks that start at exactly the same date and time. It does not look at durations, so a 30-minute walk at 07:30 and a feeding at 07:45 would not be flagged even though they overlap. I kept it that way because exact-match checking is simple, easy to test and easy to explain, and a pet owner usually schedules in clean slots like 07:30 or 08:00. The cost is that overlaps can slip through, so the extra `next_available_slot` helper (see the README) does take durations into account when it looks for a free spot.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used Claude Code in agent mode for this project. It drafted the UML, generated the class skeleton, implemented the classes, wrote the CLI demo and the tests, and wired up the Streamlit app, and the work went through the phases in order with a separate git commit for each one. The most useful prompts were specific ones that named a file and a behavior, like "make the Scheduler read tasks through `Owner.get_all_tasks()`" or "return warning strings instead of raising". For the optional model comparison I also asked two different models to write the same free-slot function (see `ai_interactions.md`).

The agent features that helped most were editing several files in one go (for example recurrence touched `pawpal_system.py`, `main.py`, the tests and the README) and running the tests and the demo right after each change. I did not use separate chat sessions for each phase; I worked in one continuous session and used a separate git commit per phase to stay organized. Looking back, a fresh session for testing would probably have given a cleaner test plan.

To be upfront about who did what: the AI wrote most of the code and text in this project, and my part was directing it, reading the output, and checking it by running the demo, the tests and the app.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

A more compact conflict-detection algorithm was possible (for example using `itertools.combinations` over all task pairs, or a one-line `all(...)` overlap test). I kept the dictionary-based `find_conflicts` and an explicit `any(start < b_end and end > b_start ...)` check in `next_available_slot`, because they are easier to read and explain even though they are a few lines longer. In the model comparison, one model's written explanation traced an example by hand and got the wrong answer (it said a 30-minute block would land at 08:15 when its own code, correctly, returns 07:00), so I did not trust the explanation. I ran both models' code on the same seven cases to check them instead, and I confirmed my own version with tests like `test_next_available_slot_skips_busy_blocks`.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

I tested sorting (tasks added out of order come back chronologically), recurrence (daily gives tomorrow, weekly gives +7 days, a one-time task gives nothing), conflict detection (same time flagged, different times/days/completed tasks not flagged), filtering, validation of bad times and priorities, priority sorting, the free-slot finder, and the JSON save/load round trip. These matter because the scheduler's whole job is to be trustworthy about order, repeats and clashes, and those are easy to get subtly wrong (for example an off-by-one on dates, or sorting `"9:00"` after `"10:00"` as text).

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

About 4 out of 5. All 23 tests pass and the CLI demo and Streamlit app behave as expected, but conflict detection only compares exact start times and I only checked the UI with Streamlit's test harness and a manual run. With more time I would test overlapping durations, tasks that cross midnight, weekly tasks completed late (should the next one be due a week from the old due date or from today?), and a corrupted `data.json`.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

I'm most satisfied with the separation between the logic layer and the UI. Building and checking everything in `main.py` and the tests first meant the Streamlit app was mostly just calls to methods that already worked, so wiring it up went smoothly.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

I would make conflict detection duration-aware so a 30-minute walk at 07:30 conflicts with a feeding at 07:45, let a task be edited or deleted from the UI, and handle several owners. I would also reconsider storing times as `"HH:MM"` strings and use `datetime` objects everywhere.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

Designing the classes and their relationships first made the AI's output much easier to check, because I had a diagram to compare it against. I also learned that AI explanations can be wrong even when its code is right, so I should verify by running things rather than trusting the description.
