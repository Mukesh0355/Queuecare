"""Patient view: check waits, book a slot, and track a live appointment."""

from datetime import datetime

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from logic.database import (
    book_slot,
    cancel_booking,
    generate_slots,
    get_appointment_status,
    get_doctors,
    get_emergency_delay,
    get_queue,
    get_taken_slots,
    patients_ahead,
)
from logic.triage import triage
from model.predict import predict_wait

DISCLAIMER = (
    "This is triage support, not a diagnosis. In a real emergency, call an ambulance."
)


def _doctor_label(doc: dict) -> str:
    return f"{doc['id']} – {doc['name']} ({doc['specialty']}, ~{doc['avg_consult_min']} min)"


def _busy_label(n_waiting: int) -> str:
    if n_waiting <= 1:
        return "Quiet"
    if n_waiting <= 4:
        return "Moderate"
    return "Busy"


def _slot_wait_minutes(doctor, slot, delay, treat_as_emergency: bool) -> tuple:
    """Return (people_ahead, model_wait, displayed_wait) for one slot."""
    now = datetime.now()
    hour = int(slot.split(" ")[1].split(":")[0])
    ahead = patients_ahead(doctor["id"], slot)
    base = predict_wait(doctor["id"], hour, now.weekday(), ahead)
    extra = 0 if treat_as_emergency else delay
    return ahead, base, base + extra


def render_patient():
    tab_wait, tab_book, tab_mine = st.tabs(
        ["Check Wait Times", "Book Appointment", "My Appointment"]
    )

    doctors = get_doctors()
    if not doctors:
        st.warning("No doctors found. Restart the app so the database can be created.")
        return

    with tab_wait:
        _render_wait_tab(doctors)
    with tab_book:
        _render_book_tab(doctors)
    with tab_mine:
        _render_my_appointment_tab()


def _render_wait_tab(doctors):
    st.subheader("Check wait times")
    st.caption("No booking needed. Pick a doctor to see how busy they are right now.")

    labels = [_doctor_label(d) for d in doctors]
    selected = st.selectbox("Doctor", labels, key="wait_doctor")
    doctor = doctors[labels.index(selected)]

    queue = get_queue(doctor["id"])
    n_waiting = len(queue)
    now = datetime.now()
    delay = get_emergency_delay(doctor["id"])
    base = predict_wait(doctor["id"], now.hour, now.weekday(), n_waiting)
    total = base + delay
    naive = n_waiting * doctor["avg_consult_min"]
    crowd = _busy_label(n_waiting)

    c1, c2, c3 = st.columns(3)
    c1.metric("People waiting now", n_waiting)
    c2.metric("Estimated wait", f"{total} min")
    c3.metric("Clinic feel", crowd)

    st.info(
        f"{n_waiting} patients ahead x {doctor['avg_consult_min']} min average "
        f"= about {naive} min"
    )
    st.caption(f"Model estimate: {base} min" + (f" + {delay} min emergency delay" if delay else ""))

    if delay > 0:
        st.warning(
            f"An emergency case is currently being treated. "
            f"Waits are about {delay} minutes longer than usual."
        )


def _render_book_tab(doctors):
    st.subheader("Book an appointment")
    st.caption("Choose a doctor, describe symptoms, and pick a 15-minute slot.")

    labels = [_doctor_label(d) for d in doctors]
    selected = st.selectbox("Doctor", labels, key="book_doctor")
    doctor = doctors[labels.index(selected)]

    name = st.text_input("Your name", key="book_name")
    age_text = st.text_input("Age", key="book_age", placeholder="e.g. 34")
    symptoms = st.text_area(
        "Symptoms (plain language is fine)",
        key="book_symptoms",
        placeholder="e.g. mild headache, high fever, chest pain…",
    )

    flags = triage(symptoms)
    if flags["level"] == "emergency":
        st.error(
            "Your symptoms look urgent. The doctor has been alerted and will see you first. "
            "If this is life-threatening, call an ambulance now."
        )
    elif flags["level"] == "urgent":
        st.warning(f"Urgent symptoms flagged (matched: **{flags['matched']}**). You will be seen sooner.")

    today = datetime.now()
    slots = generate_slots(today.date())
    taken = get_taken_slots(doctor["id"])
    available = [s for s in slots if s not in taken]
    if today.hour >= 17:
        st.caption("Clinic hours are 9 AM–5 PM. Today's board is still open for this prototype demo.")

    if not available:
        st.info("No open slots left for this doctor today. Try another doctor.")
        st.caption(DISCLAIMER)
        return

    delay = get_emergency_delay(doctor["id"])
    is_emergency = flags["level"] == "emergency"
    rows = []
    for slot in available:
        ahead, base, shown = _slot_wait_minutes(doctor, slot, delay, is_emergency)
        rows.append({"slot": slot, "display": slot.split(" ")[1], "ahead": ahead, "wait": shown})

    least_wait = min(r["wait"] for r in rows)
    least_slots = {r["slot"] for r in rows if r["wait"] == least_wait}

    st.markdown("**Available slots** (predicted wait includes any emergency delay)")
    options = []
    lookup = {}
    for r in rows:
        tag = "  ·  Least crowded" if r["slot"] in least_slots else ""
        label = f"{r['display']}  —  ~{r['wait']} min wait{tag}"
        options.append(label)
        lookup[label] = r

    chosen = st.selectbox("Pick a time", options, key="book_slot")
    chosen_row = lookup[chosen]
    naive = chosen_row["ahead"] * doctor["avg_consult_min"]
    st.caption(
        f"{chosen_row['ahead']} patients ahead x {doctor['avg_consult_min']} min average "
        f"= about {naive} min. Displayed wait: **{chosen_row['wait']} min**."
    )

    if st.button("Book appointment", type="primary", key="book_submit"):
        if not (name or "").strip():
            st.error("Please enter your name.")
            return
        if not (age_text or "").strip():
            st.error("Please enter your age.")
            return
        if not (symptoms or "").strip():
            st.error("Please describe your symptoms (even a short note is fine).")
            return
        try:
            age = int(age_text)
        except ValueError:
            st.error("Age must be a whole number.")
            return
        if age < 0 or age > 120:
            st.error("Please enter a realistic age (0–120).")
            return
        try:
            appointment_id = book_slot(
                patient_name=name,
                age=age,
                doctor_id=doctor["id"],
                slot_time=chosen_row["slot"],
                symptoms=symptoms,
            )
        except ValueError as exc:
            st.error(str(exc))
            return

        st.session_state["tracked_appointment_id"] = str(appointment_id)
        result = triage(symptoms)
        st.success(
            f"Booked. Your appointment ID is **{appointment_id}**. "
            f"Please save this ID — you will need it on the My Appointment tab. "
            f"{doctor['name']} at **{chosen_row['display']}**, "
            f"estimated wait **{chosen_row['wait']} min**."
        )
        if result["level"] == "emergency":
            st.error(
                "Your symptoms look urgent. The doctor has been alerted and will see you first. "
                "If this is life-threatening, call an ambulance now."
            )

    st.caption(DISCLAIMER)


def _render_my_appointment_tab():
    st.subheader("My appointment")
    st.caption("Enter your appointment ID. This tab refreshes every 5 seconds.")

    if "tracked_appointment_id" not in st.session_state:
        st.session_state.tracked_appointment_id = ""

    # Keep the typed ID across auto-refresh by binding the widget to session_state.
    st.text_input("Appointment ID", key="tracked_appointment_id")
    raw_id = (st.session_state.tracked_appointment_id or "").strip()

    if raw_id:
        st_autorefresh(interval=5000, key="my_appt_refresh")

    if not raw_id:
        st.info("Type the appointment ID from your booking confirmation.")
        return

    try:
        int(raw_id)
    except ValueError:
        st.error("Appointment ID must be a number.")
        return

    status = get_appointment_status(raw_id)
    if status["status"] == "not_found":
        st.error("No appointment found for that ID.")
        return

    if status["status"] == "cancelled":
        st.warning("This appointment was cancelled.")
        return
    if status["status"] == "seen":
        st.success("This visit is complete. Thank you.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Position in queue", status["position"] or "—")
    c2.metric("Base wait", f"{status['base_wait']} min")
    c3.metric("Emergency delay", f"{status['delay']} min")
    c4.metric("Total wait", f"{status['total_wait']} min")

    st.caption(
        f"Triage: **{status['triage_level']}** · "
        f"Emergency ahead: {'yes' if status['emergency_active'] else 'no'}"
    )

    if status["delay"] > 0:
        st.warning(
            f"An emergency case was prioritized. Your wait increased by "
            f"{status['delay']} min. Thank you for your patience."
        )

    if st.button("Cancel Appointment", key="cancel_appt"):
        cancel_booking(raw_id)
        st.success("Appointment cancelled.")
        st.rerun()
