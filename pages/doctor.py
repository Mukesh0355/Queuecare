"""Doctor view: live queue with triage colours and a Mark as Seen action."""

import math
import time

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from logic.database import complete_visit, get_doctors, get_emergency_delay, get_queue
from logic.auth import current_doctor_id, get_pins, login, logout


TRIAGE_COLORS = {
    "emergency": "#d32f2f",
    "urgent": "#ef6c00",
    "routine": "#2e7d32",
}


def _style_triage(column: pd.Series):
    styles = []
    for value in column:
        color = TRIAGE_COLORS.get(str(value), "#555555")
        styles.append(f"background-color: {color}; color: white; font-weight: 600")
    return styles


def _doctor_label(doctor):
    return f"{doctor['name']} ({doctor['specialty']})"


def _render_login(doctors):
    get_pins()
    locked_until = st.session_state.get("doctor_login_locked_until", 0)
    remaining = max(0, math.ceil(locked_until - time.time()))
    if locked_until and not remaining:
        st.session_state["doctor_login_attempts"] = 0
        st.session_state["doctor_login_locked_until"] = 0

    st.subheader("Doctor login")
    if remaining:
        st.error(f"Too many failed attempts. Try again in {remaining} seconds.")
        st_autorefresh(interval=1000, key="doctor_login_lock_refresh")

    with st.form("doctor_login_form"):
        doctor_index = st.selectbox(
            "Doctor",
            range(len(doctors)),
            format_func=lambda index: _doctor_label(doctors[index]),
            key="doctor_login_id",
            disabled=bool(remaining),
        )
        pin = st.text_input(
            "PIN",
            type="password",
            key="doctor_login_pin",
            disabled=bool(remaining),
        )
        submitted = st.form_submit_button("Log in", disabled=bool(remaining))

    if submitted and not remaining:
        doctor_id = str(doctors[doctor_index]["id"])
        if login(doctor_id, pin):
            st.session_state["auth_doctor_id"] = int(doctor_id)
            st.session_state["doctor_login_attempts"] = 0
            st.session_state["doctor_login_locked_until"] = 0
            st.session_state.pop("doctor_login_error", None)
            st.rerun()

        attempts = st.session_state.get("doctor_login_attempts", 0) + 1
        st.session_state["doctor_login_attempts"] = attempts
        st.session_state["doctor_login_error"] = True
        if attempts >= 5:
            st.session_state["doctor_login_locked_until"] = time.time() + 60
        st.rerun()

    if st.session_state.pop("doctor_login_error", False):
        st.error("Wrong PIN")


def render_doctor():
    doctors = get_doctors()
    if not doctors:
        st.warning("No doctors found.")
        return

    doctor_id = current_doctor_id()
    doctor = next((d for d in doctors if d["id"] == doctor_id), None)
    if doctor is None:
        logout()
        _render_login(doctors)
        return

    st.write(f"Signed in as {doctor['name']}")
    if st.button("Log out", key="doctor_logout"):
        logout()
        st.rerun()

    st.subheader("Live queue")
    st.caption("Refreshes every 3 seconds. Emergencies always appear at the top.")
    st_autorefresh(interval=3000, key="doctor_queue_refresh")

    queue = get_queue(doctor_id)
    emergencies = [p for p in queue if p["triage_level"] == "emergency"]
    routine = [p for p in queue if p["triage_level"] == "routine"]
    delay = get_emergency_delay(doctor_id)

    if emergencies:
        for p in emergencies:
            keyword = p["matched_keyword"] or "keyword"
            st.error(
                f"EMERGENCY — {p['patient_name']}, age {p['age']}. "
                f"Symptoms: {p['symptoms'] or '(none given)'}. "
                f"Matched keyword: **{keyword}**. "
                f"This is adding about {delay} minutes to other patients' waits."
            )

    c1, c2, c3 = st.columns(3)
    c1.metric("Patients waiting", len(queue))
    c2.metric("Routine patients affected", len(routine) if emergencies else 0)
    c3.metric("Emergency extra wait", f"{delay} min")

    if not queue:
        st.info("Queue is empty. No one is waiting right now.")
        return

    table = pd.DataFrame(
        [
            {
                "ID": p["appointment_id"],
                "Patient": p["patient_name"],
                "Age": p["age"],
                "Slot": str(p["slot_time"]).split(" ")[-1],
                "Triage": p["triage_level"],
                "Keyword": p["matched_keyword"] or "—",
                "Symptoms": p["symptoms"] or "—",
            }
            for p in queue
        ]
    )
    styled = table.style.apply(_style_triage, subset=["Triage"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("#### Complete a visit")
    for p in queue:
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.write(
                f"**{p['patient_name']}** (age {p['age']}) · "
                f"{p['triage_level']} · slot {str(p['slot_time']).split(' ')[-1]}"
            )
        with col_btn:
            if st.button("Mark as Seen", key=f"seen_{p['appointment_id']}"):
                if not complete_visit(p["appointment_id"], doctor_id):
                    st.warning("This appointment is no longer in your queue.")
                    return
                st.rerun()
