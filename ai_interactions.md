# AI Interactions Log

> Only the stretch (optional) challenges I attempted are documented here.

---

## Agent Workflow (Challenge 1: Advanced Algorithmic Capability)

**What task did you give the agent?**

Add a third algorithmic capability beyond sorting, filtering, recurrence and conflict warnings: a "next available slot" finder that takes task durations into account.

**What did the agent do?**

- `pawpal_system.py`: added `Scheduler.next_available_slot(duration, day, day_start, day_end, step)` plus the helpers `to_minutes()` and `to_hhmm()`.
- `tests/test_pawpal.py`: added tests for a normal day, an empty day and a task longer than the whole day.
- `main.py`: added a "Next free 45-minute slot today" section to the demo.
- `app.py`: added a "Find a free slot" section, and made the conflict warning suggest the next free slot.
- `README.md`: documented the method in the Smarter Scheduling table.

**What did you have to verify or fix manually?**

I ran the tests and the demo. Along the way the generated file also had a string-escaping slip in `format_schedule` (an actual line break inside a string literal) that caused a `SyntaxError`, which was caught immediately when the code was imported and fixed. I also added a Date column to the schedule table after the demo showed tomorrow's recurring task sorted after today's with nothing to explain why.

---

## Prompt Comparison (Challenge 5: Multi-Model Prompt Comparison)

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | Claude Sonnet | Claude Haiku |
| **Prompt** | Same prompt for both: write `next_available_slot(busy, duration, day_start="07:00", day_end="21:00", step=15)` that returns the earliest "HH:MM" where the block fits without overlapping busy `(start, minutes)` intervals, or None; reply with the code, a short explanation and the time complexity. | (same) |
| **Response summary** | Converts times to minutes, walks the day in `step` increments, and uses `all(end <= b_start or start >= b_end ...)` to test that the block is clear of every busy interval. Explains it as O(S x B). | Same overall approach and the same helpers, but tests for a clash with `any(candidate < b_end and block_end > b_start ...)` and builds the busy list with a plain loop. Also O(W x n). |
| **What was useful** | Compact, with good comments, and its closing note that sorting and merging the busy intervals would reduce the cost for large inputs. | Slightly more readable: the variable `clashes` and the "any overlap" test read like the English definition of overlap. Its explanation of the example was correct. |
| **Problems noticed** | The code was correct, but the written example was wrong: it said 30 minutes would be placed at 08:15, while its own code returns 07:00 (the block 07:00-07:30 only touches the 07:30 task). Its note also said it did not run the code, only traced it by hand. | No functional problems. It is a little longer because of the explicit loop for building the busy ranges. |
| **Decision** | Not used as-is. | Used its overlap test (`any(...)`) in `Scheduler.next_available_slot`. |

I ran both functions on seven inputs (an empty day, a fully busy day, duration 0, duration longer than the day and the cases from the prompt) and they returned identical results every time, so the choice came down to readability. **Which approach did you use in your final implementation and why?** The "any overlap" form from Option B, since it matches the plain-English definition of overlap and is easier to explain, with the slightly more compact comments from Option A. Lesson: both models wrote correct code, but a model's own worked example is not evidence, so I verified by running it.
