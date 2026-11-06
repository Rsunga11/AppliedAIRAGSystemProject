import json
from datetime import date

import pytest

from advisor import CareAdvisor
from agent import CarePlanAgent, find_overlaps, format_trace, trace_to_json
from pawpal_system import Owner, Pet, Scheduler, Task
from retriever import KnowledgeBase

TODAY = date(2026, 11, 5)


@pytest.fixture(scope="module")
def agent():
    return CarePlanAgent(CareAdvisor(KnowledgeBase()))


def make_owner():
    owner = Owner("Jordan")
    dog, cat = Pet("Biscuit", "dog"), Pet("Mochi", "cat")
    owner.add_pet(dog)
    owner.add_pet(cat)
    return owner, dog, cat


# ------------------------------------------------------------- find_overlaps
def test_find_overlaps_catches_what_exact_time_matching_misses():
    owner, dog, _ = make_owner()
    dog.add_task(Task("Long walk", "07:00", 60, due_date=TODAY))
    dog.add_task(Task("Feed", "07:30", 10, due_date=TODAY))
    assert Scheduler(owner).find_conflicts() == []  # different start times
    assert len(find_overlaps(owner, TODAY)) == 1  # but the walk is still running


def test_back_to_back_tasks_do_not_overlap():
    owner, dog, _ = make_owner()
    dog.add_task(Task("Walk", "07:00", 30, due_date=TODAY))
    dog.add_task(Task("Feed", "07:30", 10, due_date=TODAY))
    assert find_overlaps(owner, TODAY) == []


# ------------------------------------------------------------------ agent run
def test_run_never_changes_real_data(agent):
    owner, dog, _ = make_owner()
    before = len(owner.get_all_tasks())
    result = agent.run(owner, dog, day=TODAY)
    assert result.proposals
    assert len(owner.get_all_tasks()) == before  # proposals only, nothing added


def test_trace_has_plan_act_check_and_done(agent):
    owner, dog, _ = make_owner()
    result = agent.run(owner, dog, day=TODAY)
    phases = [step["phase"] for step in result.trace]
    assert phases[0] == "plan" and phases[1] == "act"
    assert "check" in phases and phases[-1] == "done"


def test_agent_replans_around_existing_tasks_until_conflict_free(agent):
    owner, dog, cat = make_owner()
    dog.add_task(Task("Vet call", "07:30", 20, "high", due_date=TODAY))
    cat.add_task(Task("Bedtime cuddle", "18:10", 30, due_date=TODAY))
    result = agent.run(owner, dog, day=TODAY)
    assert any(step["phase"] == "replan" for step in result.trace)
    assert result.unresolved == []
    # after the human approves everything, the real schedule has no conflicts or overlaps
    CarePlanAgent.apply(dog, result)
    assert Scheduler(owner).find_conflicts() == []
    assert find_overlaps(owner, TODAY) == []


def test_pet_that_already_has_the_routine_gets_no_proposals(agent):
    owner, _, cat = make_owner()
    for description, time in [("Breakfast", "08:00"), ("Dinner", "18:30"), ("Play", "12:00"), ("Evening play", "20:00"), ("Litter scoop", "09:00")]:
        cat.add_task(Task(description, time, 10, due_date=TODAY))
    result = agent.run(owner, cat, day=TODAY)
    assert result.proposals == []
    assert result.confidence == 0.0


def test_unfixable_day_is_flagged_for_human_review(agent):
    owner, dog, _ = make_owner()
    dog.add_task(Task("All-day appointment", "07:00", 840, "high", due_date=TODAY))  # fills 07:00-21:00
    result = agent.run(owner, dog, day=TODAY)
    assert result.unresolved
    assert result.needs_review


def test_pet_must_belong_to_owner(agent):
    owner, _, _ = make_owner()
    with pytest.raises(ValueError):
        agent.run(owner, Pet("Stranger", "dog"))


# ----------------------------------------------------------- human-in-the-loop
def test_apply_adds_only_approved_proposals(agent):
    owner, dog, _ = make_owner()
    result = agent.run(owner, dog, day=TODAY)
    added = CarePlanAgent.apply(dog, result, approved=[0])
    assert len(added) == 1 and len(dog.tasks) == 1
    assert dog.tasks[0].due_date == TODAY


def test_apply_with_nothing_approved_adds_nothing(agent):
    owner, dog, _ = make_owner()
    result = agent.run(owner, dog, day=TODAY)
    assert CarePlanAgent.apply(dog, result, approved=[]) == []
    assert dog.tasks == []


# ---------------------------------------------------------------- trace output
def test_trace_formats_as_text_and_valid_json(agent):
    owner, dog, _ = make_owner()
    result = agent.run(owner, dog, day=TODAY)
    text = format_trace(result)
    assert "Agent trace for Biscuit" in text and "[PLAN" in text
    data = json.loads(trace_to_json(result))
    assert data["pet"] == "Biscuit" and data["proposals"] and data["trace"]
