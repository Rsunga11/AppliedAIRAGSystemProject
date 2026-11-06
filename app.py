import os
from datetime import date

import streamlit as st

from advisor import CareAdvisor, configure_logging
from agent import CarePlanAgent, format_trace
from llm import from_env
from pawpal_system import PRIORITY_ICONS, Owner, Pet, Scheduler, Task, task_icon
from retriever import KnowledgeBase

DATA_FILE = "data.json"

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")
st.caption("A pet care planner that sorts, filters, repeats tasks, warns you about conflicts, and has an AI care advisor.")

configure_logging()


@st.cache_resource
def load_advisor() -> CareAdvisor:
    """Build the retrieval index once. Uses Gemini only if GEMINI_API_KEY is set; otherwise fully offline."""
    return CareAdvisor(KnowledgeBase(), llm=from_env())


advisor = load_advisor()
agent = CarePlanAgent(advisor)


def show_review(review) -> None:
    """Show an advisor review of a task with its confidence and source."""
    detail = f" (confidence {review.confidence:.2f}; source: {', '.join(review.sources)})" if review.sources else ""
    if review.status == "warn":
        st.warning("🩺 Advisor: " + " ".join(review.messages) + detail)
    elif review.status == "ok":
        st.info("🩺 Advisor: " + " ".join(review.messages) + detail)
    else:
        st.caption("🩺 Advisor: no care guidance for this kind of task, so it was not checked.")


# Streamlit reruns this whole script on every click, so the Owner has to live in
# session_state. On the very first run we also try to load saved data.
if "owner" not in st.session_state:
    if os.path.exists(DATA_FILE):
        st.session_state.owner = Owner.load_from_json(DATA_FILE)
    else:
        st.session_state.owner = Owner("Jordan")
owner = st.session_state.owner
scheduler = Scheduler(owner)


def save() -> None:
    """Persist the owner's data so it survives a restart."""
    owner.save_to_json(DATA_FILE)


# ---------------------------------------------------------------- owner + pets
owner.name = st.text_input("Owner name", value=owner.name)

st.subheader("1. Add a pet")
with st.form("add_pet", clear_on_submit=True):
    pet_name = st.text_input("Pet name")
    species = st.selectbox("Species", ["dog", "cat", "other"])
    if st.form_submit_button("Add pet"):
        if not pet_name.strip():
            st.error("Give your pet a name.")
        elif any(p.name.lower() == pet_name.strip().lower() for p in owner.pets):
            st.error(f"You already have a pet named {pet_name.strip()}.")
        else:
            owner.add_pet(Pet(pet_name.strip(), species))
            save()
            st.success(f"Added {pet_name.strip()}!")

if owner.pets:
    st.write("Your pets: " + ", ".join(f"{p.name} ({p.species})" for p in owner.pets))

# ---------------------------------------------------------------------- tasks
st.subheader("2. Schedule a task")
if owner.pets:
    with st.form("add_task", clear_on_submit=True):
        pet_choice = st.selectbox("Pet", [p.name for p in owner.pets])
        description = st.text_input("Task", value="Morning walk")
        c1, c2 = st.columns(2)
        with c1:
            task_date = st.date_input("Date", value=date.today())
            time_value = st.time_input("Time")
            priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
        with c2:
            duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
            frequency = st.selectbox("Repeats", ["once", "daily", "weekly"])
        if st.form_submit_button("Add task"):
            if not description.strip():
                st.error("Describe the task first.")
            else:
                pet = next(p for p in owner.pets if p.name == pet_choice)
                new_task = Task(
                    description.strip(),
                    time_value.strftime("%H:%M"),
                    int(duration),
                    priority,
                    frequency,
                    due_date=task_date,
                )
                pet.add_task(new_task)
                save()
                st.success(f"Added '{description.strip()}' for {pet_choice}.")
                show_review(advisor.review_task(pet, new_task))  # RAG-backed check of the new task
else:
    st.info("Add a pet first, then you can schedule tasks for it.")

# ------------------------------------------------------------------- conflicts
conflicts = scheduler.find_conflicts()
for message in conflicts:
    st.warning(
        f"⚠️ {message}. You can't be in two places at once, so move one of them. "
        f"The next free 30-minute slot today is {scheduler.next_available_slot(30) or 'not available'}."
    )

# -------------------------------------------------------------------- schedule
st.subheader("3. Your schedule")
col_a, col_b, col_c = st.columns(3)
with col_a:
    pet_filter = st.selectbox("Pet", ["All pets"] + [p.name for p in owner.pets])
with col_b:
    status_filter = st.selectbox("Status", ["All", "To do", "Done"])
with col_c:
    sort_mode = st.selectbox("Sort by", ["Time", "Priority, then time"])

tasks = scheduler.filter_tasks(
    pet_name=None if pet_filter == "All pets" else pet_filter,
    completed={"All": None, "To do": False, "Done": True}[status_filter],
)
tasks = scheduler.sort_by_time(tasks) if sort_mode == "Time" else scheduler.sort_by_priority_then_time(tasks)

if tasks:
    st.table(
        [
            {
                "Done": "✅" if t.completed else "⏳",
                "Date": t.due_date.isoformat(),
                "Time": t.time,
                "Task": f"{task_icon(t.description)} {t.description}",
                "Pet": scheduler.pet_for(t).name,
                "Min": t.duration_minutes,
                "Priority": f"{PRIORITY_ICONS[t.priority]} {t.priority}",
                "Repeats": t.frequency,
            }
            for t in tasks
        ]
    )
    if not conflicts:
        st.success("No scheduling conflicts. 🎉")

    open_tasks = [t for t in tasks if not t.completed]
    if open_tasks:
        st.markdown("**Mark a task done**")
        labels = {f"{t.due_date} {t.time} - {t.description} ({scheduler.pet_for(t).name})": t for t in open_tasks}
        chosen = st.selectbox("Task", list(labels))
        if st.button("Mark complete"):
            follow_up = scheduler.mark_task_complete(labels[chosen])
            save()
            if follow_up:
                st.success(f"Done! A new '{follow_up.description}' was added for {follow_up.due_date}.")
            else:
                st.success("Done!")
            st.rerun()
else:
    st.info("No tasks match. Add one above.")

# ------------------------------------------------------------ free slot finder
st.subheader("4. Find a free slot")
slot_minutes = st.number_input("How many minutes do you need?", min_value=5, max_value=240, value=30, step=5)
slot_day = st.date_input("On which day?", value=date.today(), key="slot_day")
if st.button("Find next free slot"):
    slot = scheduler.next_available_slot(int(slot_minutes), day=slot_day)
    if slot:
        st.success(f"Earliest free {int(slot_minutes)}-minute slot on {slot_day}: {slot}")
    else:
        st.warning("No free slot of that length between 07:00 and 21:00.")

# ------------------------------------------------------------ AI: ask the advisor
st.subheader("5. Ask the Care Advisor")
st.caption(
    "Answers come from the pet-care notes in `knowledge/` (retrieval), not from guesswork. "
    + ("Gemini is on: it rewrites the retrieved notes." if advisor.llm else "Offline mode: answers come straight from the notes.")
)
question = st.text_input("Your question", placeholder="How long should I walk my dog?")
ask_species = st.selectbox("About which pet type?", ["any", "dog", "cat", "other"])
if st.button("Ask"):
    answer = advisor.answer_question(question, None if ask_species == "any" else ask_species)
    if answer.refused:
        st.warning(answer.text)
    else:
        st.write(answer.text)
        st.caption(
            f"Confidence: {answer.confidence:.2f} | "
            + ("Explained by Gemini from the notes" if answer.used_llm else "Answered from local notes (offline)")
        )
        if answer.needs_review:
            st.warning("Low confidence: please double-check with a veterinarian.")
        if answer.sources:
            with st.expander("Sources"):
                for source in answer.sources:
                    st.write("• " + source)

# ----------------------------------------------------------- AI: care plan agent
st.subheader("6. Suggest a care plan (AI agent)")
st.caption("The agent proposes routine tasks, checks them for conflicts, fixes what it can, and waits for your approval.")
if owner.pets:
    plan_pet_name = st.selectbox("Pet", [p.name for p in owner.pets], key="plan_pet")
    if st.button("Suggest a plan"):
        plan_pet = next(p for p in owner.pets if p.name == plan_pet_name)
        st.session_state.plan = (plan_pet.name, agent.run(owner, plan_pet))

    if "plan" in st.session_state:
        planned_name, result = st.session_state.plan
        planned_pet = next((p for p in owner.pets if p.name == planned_name), None)
        if planned_pet is None or not result.proposals:
            st.info(f"Nothing to add: {planned_name} already has the routine tasks I know about.")
        else:
            st.markdown(f"**Proposed tasks for {planned_name}** (confidence {result.confidence:.2f})")
            approved = []
            for index, proposal in enumerate(result.proposals):
                label = f"{task_icon(proposal.description)} {proposal.time} - {proposal.description} ({proposal.duration_minutes} min, {proposal.priority})"
                if st.checkbox(label, value=True, key=f"approve_{index}"):
                    approved.append(index)
            if result.needs_review:
                st.warning("The agent could not fully resolve these issues, so please review: " + " | ".join(result.unresolved))
            with st.expander("Agent reasoning trace"):
                st.code(format_trace(result))
            if st.button("Add approved tasks"):
                added = agent.apply(planned_pet, result, approved)
                save()
                del st.session_state.plan
                st.success(f"Added {len(added)} task(s) to {planned_name}.")
                st.rerun()
else:
    st.info("Add a pet first.")
