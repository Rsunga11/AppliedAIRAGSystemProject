import streamlit as st

from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")

# Streamlit reruns this script on every click, so the Owner has to live in
# session_state or it would be recreated (empty) each time.
if "owner" not in st.session_state:
    st.session_state.owner = Owner("Jordan")
owner = st.session_state.owner

st.subheader("Add a pet")
with st.form("add_pet", clear_on_submit=True):
    pet_name = st.text_input("Pet name")
    species = st.selectbox("Species", ["dog", "cat", "other"])
    if st.form_submit_button("Add pet"):
        if pet_name.strip():
            owner.add_pet(Pet(pet_name.strip(), species))
        else:
            st.error("Give your pet a name.")

st.subheader("Schedule a task")
if owner.pets:
    with st.form("add_task", clear_on_submit=True):
        pet_choice = st.selectbox("Pet", [p.name for p in owner.pets])
        description = st.text_input("Task", value="Morning walk")
        time_value = st.time_input("Time")
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
        if st.form_submit_button("Add task"):
            pet = next(p for p in owner.pets if p.name == pet_choice)
            pet.add_task(Task(description, time_value.strftime("%H:%M"), int(duration), priority))
else:
    st.info("Add a pet first, then you can schedule tasks for it.")

st.subheader("Today's schedule")
schedule = Scheduler(owner).get_todays_schedule()
if schedule:
    st.table(
        [{"Time": t.time, "Task": t.description, "Duration": t.duration_minutes, "Priority": t.priority} for t in schedule]
    )
else:
    st.info("No tasks yet.")
