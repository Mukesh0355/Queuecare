"""Doctor view: live queue with triage colours and a Mark as Seen action."""

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from logic.database import complete_visit, get_doctors, get_emergency_delay, get_queue


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


def render_doctor():
    st.subheader("Live queue")
    st.caption("Refreshes every 3 seconds. Emergencies always appear at the top.")

    st_autorefresh(interval=3000, key="doctor_queue_refresh")

    doctors = get_doctors()
    if not doctors:
        st.warning("No doctors found.")
        return

    labels = [f"{d['id']} – {d['name']} ({d['specialty']})" for d in doctors]
    selected = st.selectbox("Signed in as", labels, key="doctor_select")
    doctor = doctors[labels.index(selected)]

    queue = get_queue(doctor["id"])
    emergencies = [p for p in queue if p["triage_level"] == "emergency"]
    routine = [p for p in queue if p["triage_level"] == "routine"]
    delay = get_emergency_delay(doctor["id"])

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
                complete_visit(p["appointment_id"])
                st.rerun()
