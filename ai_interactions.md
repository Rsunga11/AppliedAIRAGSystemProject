# AI Interactions Log

## Agentic Workflow Enhancement: multi-step reasoning traces

The Care Plan Agent (`agent.py`) works in four steps: **plan** (retrieve care guidance and list the routine tasks a pet is missing), **act** (place them in a scratch copy of the schedule), **check** (look for overlapping tasks that involve its own proposals, and review each task against retrieved guidance), and **re-plan** (move conflicting tasks to the next free slot, then check again, up to 3 rounds). It only proposes: a human approves before anything is added. Every step is written to the trace and to `logs/pawpal.log`.

### Trace 1: conflicts found and fixed (Rex already has a 07:30 vet call)

The agent proposed 5 tasks, found overlaps, moved 5 of them to free slots in round 1, re-checked in round 2 and found the plan consistent. The real data was untouched until the human approved three proposals.

```
== Agent: plan -> act -> check -> re-plan (proposals only) ==
Agent trace for Rex:
   1. [PLAN  ] (round 0) Retrieved guidance for dog; proposing 5 task(s): Morning walk @ 07:30, Evening walk @ 18:00, Morning feeding @ 07:30, Evening feeding @ 18:00, Play session @ 18:00
   2. [ACT   ] (round 0) Placed all proposals at their preferred times in a scratch copy (real data untouched).
   3. [CHECK ] (round 1) 12 problem(s): Flea medicine (Mochi) overlaps Morning feeding (Rex) around 07:30 | Flea medicine (Mochi) overlaps Morning walk (Rex) around 07:30 | Morning feeding (Rex) overlaps Vet call (Rex) around 07:30 | Morning feeding (Rex) overlaps Morning walk (Rex) around 07:30 | Vet call (Rex) overlaps Morning walk (Rex) around 07:30 | Morning walk (Rex) overlaps Breakfast (Mochi) around 08:00 | Evening feeding (Rex) overlaps Play session (Rex) around 18:00 | Evening feeding (Rex) overlaps Evening walk (Biscuit) around 18:00 | Evening feeding (Rex) overlaps Evening walk (Rex) around 18:00 | Play session (Rex) overlaps Evening walk (Biscuit) around 18:00 | Play session (Rex) overlaps Evening walk (Rex) around 18:00 | Evening walk (Biscuit) overlaps Evening walk (Rex) around 18:00
   4. [REPLAN] (round 1) Moved 'Morning walk' from 07:30 to 08:15 (next free slot).
   5. [REPLAN] (round 1) Moved 'Evening walk' from 18:00 to 18:30 (next free slot).
   6. [REPLAN] (round 1) Moved 'Morning feeding' from 07:30 to 09:00 (next free slot).
   7. [REPLAN] (round 1) Moved 'Evening feeding' from 18:00 to 19:15 (next free slot).
   8. [REPLAN] (round 1) Moved 'Play session' from 18:00 to 19:30 (next free slot).
   9. [CHECK ] (round 2) No conflicts or overlaps. Plan is consistent.
  10. [DONE  ] (round 2) 5 proposal(s) ready for approval; no open issues.
  Confidence: 0.89 | Needs review: False

Tasks on Rex BEFORE approval: 1 (only the existing 'Vet call'; the agent never edits data on its own)

== Human approval: approve the first 3 proposals ==
Added: ['Morning walk', 'Evening walk', 'Morning feeding']
   Date  Time   Task                   Pet        Min  Priority
⏳ 11-05 07:30  🏥 Vet call             Rex         20  🔴 high
⏳ 11-05 08:15  🦮 Morning walk         Rex         45  🔴 high
⏳ 11-05 09:00  🍽️ Morning feeding     Rex         12  🔴 high
⏳ 11-05 18:30  🦮 Evening walk         Rex         45  🔴 high
Overlaps involving the newly added tasks: none
```

### Trace 2: a plan the agent cannot fix (a single appointment fills 07:00-21:00)

With no free time in the day, the agent stops instead of looping forever, and flags the plan for human review rather than pretending it worked.

```
Agent trace for Busy:
   1. [PLAN  ] (round 0) Retrieved guidance for dog; proposing 5 task(s): Morning walk @ 07:30, Evening walk @ 18:00, Morning feeding @ 07:30, Evening feeding @ 18:00, Play session @ 18:00
   2. [ACT   ] (round 0) Placed all proposals at their preferred times in a scratch copy (real data untouched).
   3. [CHECK ] (round 1) 9 problem(s): All-day appointment (Busy) overlaps Morning feeding (Busy) around 07:30 | All-day appointment (Busy) overlaps Morning walk (Busy) around 07:30 | All-day appointment (Busy) overlaps Evening feeding (Busy) around 18:00 | All-day appointment (Busy) overlaps Play session (Busy) around 18:00 | All-day appointment (Busy) overlaps Evening walk (Busy) around 18:00 | Morning feeding (Busy) overlaps Morning walk (Busy) around 07:30 | Evening feeding (Busy) overlaps Play session (Busy) around 18:00 | Evening feeding (Busy) overlaps Evening walk (Busy) around 18:00 | Play session (Busy) overlaps Evening walk (Busy) around 18:00
   4. [CHECK ] (round 1) Could not resolve the remaining problems automatically; flagging for human review.
   5. [DONE  ] (round 1) 5 proposal(s) ready for approval; needs human review.
  Confidence: 0.89 | Needs review: True
```

### Trace 3: the same Rex run as structured JSON (`trace_to_json`)

```json
{
  "pet": "Rex",
  "rounds": 2,
  "confidence": 0.89,
  "unresolved": [],
  "proposals": [
    {
      "description": "Morning walk",
      "time": "08:00",
      "minutes": 45,
      "priority": "high"
    },
    {
      "description": "Evening walk",
      "time": "18:30",
      "minutes": 45,
      "priority": "high"
    },
    {
      "description": "Morning feeding",
      "time": "08:45",
      "minutes": 12,
      "priority": "high"
    },
    {
      "description": "Evening feeding",
      "time": "19:15",
      "minutes": 12,
      "priority": "high"
    },
    {
      "description": "Play session",
      "time": "18:00",
      "minutes": 22,
      "priority": "medium"
    }
  ],
  "trace": [
    {
      "step": 1,
      "round": 0,
      "phase": "plan",
      "detail": "Retrieved guidance for dog; proposing 5 task(s): Morning walk @ 07:30, Evening walk @ 18:00, Morning feeding @ 07:30, Evening feeding @ 18:00, Play session @ 18:00"
    },
    {
      "step": 2,
      "round": 0,
      "phase": "act",
      "detail": "Placed all proposals at their preferred times in a scratch copy (real data untouched)."
    },
    {
      "step": 3,
      "round": 1,
      "phase": "check",
      "detail": "6 problem(s): Morning feeding (Rex) overlaps Vet call (Rex) around 07:30 | Morning feeding (Rex) overlaps Morning walk (Rex) around 07:30 | Vet call (Rex) overlaps Morning walk (Rex) around 07:30 | Evening feeding (Rex) overlaps Play session (Rex) around 18:00 | Evening feeding (Rex) overlaps Evening walk (Rex) around 18:00 | Play session (Rex) overlaps Evening walk (Rex) around 18:00"
    },
    {
      "step": 4,
      "round": 1,
      "phase": "replan",
      "detail": "Moved 'Morning walk' from 07:30 to 08:00 (next free slot)."
    },
    {
      "step": 5,
      "round": 1,
      "phase": "replan",
      "detail": "Moved 'Evening walk' from 18:00 to 18:30 (next free slot)."
    },
    {
      "step": 6,
      "round": 1,
      "phase": "replan",
      "detail": "Moved 'Morning feeding' from 07:30 to 08:45 (next free slot)."
    },
    {
      "step": 7,
      "round": 1,
      "phase": "replan",
      "detail": "Moved 'Evening feeding' from 18:00 to 19:15 (next free slot)."
    },
    {
      "step": 8,
      "round": 2,
      "phase": "check",
      "detail": "No conflicts or overlaps. Plan is consistent."
    },
    {
      "step": 9,
      "round": 2,
      "phase": "done",
      "detail": "5 proposal(s) ready for approval; no open issues."
    }
  ]
}
```

## Test harness and how the AI-written code was checked

- `python eval_harness.py` runs 35 predefined cases and writes `logs/eval_results.txt`; the result is in the README.
- When I (with Claude Code) probed the advisor with inputs it was not designed for, the AI-written guardrails failed in three ways (missed drug names, answered a goldfish question with dog advice, returned adult-dog text for a puppy question). I fixed them and kept each as a regression test. The agent also initially counted unrelated overlaps as its own problems, which I found by reading the demo output and fixed.

## Prompts and requests that shaped the design

- "Extend PawPal+ with at least one real AI feature that changes how the system behaves, not just a standalone script" led to the retrieval-driven design (structured hints parsed from retrieved chunks).
- "Use my free Gemini key" led to the offline-first design with Gemini as an optional step, and to the rule that the key lives only in a git-ignored `.env`.
- "Make the agent propose, not act" led to the scratch-copy design and the human approval step.
