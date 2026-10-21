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

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

My conflict detection only flags tasks that start at exactly the same date and time. It does not look at durations, so a 30-minute walk at 07:30 and a feeding at 07:45 would not be flagged even though they overlap. I kept it that way because exact-match checking is simple, easy to test and easy to explain, and a pet owner usually schedules in clean slots like 07:30 or 08:00. The cost is that overlaps can slip through, so the extra `next_available_slot` helper (see the README) does take durations into account when it looks for a free spot.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
