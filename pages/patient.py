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
from logic.i18n import t
from logic.triage import triage
from model.predict import predict_wait


def _doctor_label(doc: dict) -> str:
    specialties = {
        "General Physician": "specialty_general",
        "Cardiologist": "specialty_cardiologist",
        "Pediatrician": "specialty_pediatrician",
    }
    return t(
        "doctor_label",
        id=doc["id"],
        name=doc["name"],
        specialty=t(specialties.get(doc["specialty"], "doctor_field")),
        avg=doc["avg_consult_min"],
        min_unit=t("min_unit"),
    )


def _busy_label(n_waiting: int) -> str:
    if n_waiting <= 1:
        return t("busy_quiet")
    if n_waiting <= 4:
        return t("busy_moderate")
    return t("busy_busy")


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
        [t("tab_wait"), t("tab_book"), t("tab_mine")]
    )

    doctors = get_doctors()
    if not doctors:
        st.warning(t("no_doctors"))
        return

    with tab_wait:
        _render_wait_tab(doctors)
    with tab_book:
        _render_book_tab(doctors)
    with tab_mine:
        _render_my_appointment_tab()


def _render_wait_tab(doctors):
    st.subheader(t("wait_heading"))
    st.caption(t("wait_caption"))

    doctor_index = st.selectbox(
        t("doctor_field"),
        range(len(doctors)),
        format_func=lambda index: _doctor_label(doctors[index]),
        key="wait_doctor",
    )
    doctor = doctors[doctor_index]

    queue = get_queue(doctor["id"])
    n_waiting = len(queue)
    now = datetime.now()
    delay = get_emergency_delay(doctor["id"])
    base = predict_wait(doctor["id"], now.hour, now.weekday(), n_waiting)
    total = base + delay
    naive = n_waiting * doctor["avg_consult_min"]
    crowd = _busy_label(n_waiting)

    c1, c2, c3 = st.columns(3)
    c1.metric(t("metric_waiting"), n_waiting)
    c2.metric(t("metric_estimated_wait"), f"{total} {t('min_unit')}")
    c3.metric(t("metric_clinic_feel"), crowd)

    st.info(
        t(
            "wait_formula",
            n=n_waiting,
            avg=doctor["avg_consult_min"],
            naive=naive,
            min_unit=t("min_unit"),
        )
    )
    st.caption(
        t(
            "model_estimate_delay",
            base=base,
            delay=delay,
            min_unit=t("min_unit"),
        )
        if delay
        else t("model_estimate", base=base, min_unit=t("min_unit"))
    )

    if delay > 0:
        st.warning(
            t(
                "emergency_wait_warning",
                delay=delay,
                min_unit=t("min_unit"),
            )
        )


def _render_book_tab(doctors):
    st.subheader(t("book_heading"))
    st.caption(t("book_caption"))

    doctor_index = st.selectbox(
        t("doctor_field"),
        range(len(doctors)),
        format_func=lambda index: _doctor_label(doctors[index]),
        key="book_doctor",
    )
    doctor = doctors[doctor_index]

    name = st.text_input(t("name_label"), key="book_name")
    age_text = st.text_input(
        t("age_label"),
        key="book_age",
        placeholder=t("age_placeholder"),
    )
    symptoms = st.text_area(
        t("symptoms_label"),
        key="book_symptoms",
        placeholder=t("symptoms_placeholder"),
    )

    flags = triage(symptoms)
    if flags["level"] == "emergency":
        st.error(t("emergency_alert"))
    elif flags["level"] == "urgent":
        st.warning(t("urgent_alert", kw=flags["matched"]))

    today = datetime.now()
    slots = generate_slots(today.date())
    taken = get_taken_slots(doctor["id"])
    available = [s for s in slots if s not in taken]
    if today.hour >= 17:
        st.caption(t("after_hours"))

    if not available:
        st.info(t("no_open_slots"))
        st.caption(t("disclaimer"))
        return

    delay = get_emergency_delay(doctor["id"])
    is_emergency = flags["level"] == "emergency"
    rows = []
    for slot in available:
        ahead, base, shown = _slot_wait_minutes(doctor, slot, delay, is_emergency)
        rows.append({"slot": slot, "display": slot.split(" ")[1], "ahead": ahead, "wait": shown})

    least_wait = min(r["wait"] for r in rows)
    least_slots = {r["slot"] for r in rows if r["wait"] == least_wait}

    st.markdown(t("available_slots"))
    options = []
    lookup = {}
    for r in rows:
        tag = t("least_crowded") if r["slot"] in least_slots else ""
        label = t(
            "slot_option",
            time=r["display"],
            wait=r["wait"],
            min_unit=t("min_unit"),
            tag=tag,
        )
        options.append(label)
        lookup[label] = r

    chosen = st.selectbox(t("pick_time"), options, key="book_slot")
    chosen_row = lookup[chosen]
    naive = chosen_row["ahead"] * doctor["avg_consult_min"]
    st.caption(
        t(
            "slot_wait_formula",
            n=chosen_row["ahead"],
            avg=doctor["avg_consult_min"],
            naive=naive,
            wait=chosen_row["wait"],
            min_unit=t("min_unit"),
        )
    )

    if st.button(t("book_button"), type="primary", key="book_submit"):
        if not (name or "").strip():
            st.error(t("enter_name"))
            return
        if not (age_text or "").strip():
            st.error(t("enter_age"))
            return
        if not (symptoms or "").strip():
            st.error(t("enter_symptoms"))
            return
        try:
            age = int(age_text)
        except ValueError:
            st.error(t("age_whole"))
            return
        if age < 0 or age > 120:
            st.error(t("age_range", min_age=0, max_age=120))
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
            error_keys = {
                "Patient name is required.": "booking_name_required",
                "A valid age is required.": "booking_age_required",
                "A time slot is required.": "booking_slot_required",
                "That slot is already booked. Please pick another.": "slot_taken",
            }
            error_key = error_keys.get(str(exc))
            if error_key is None:
                raise
            st.error(t(error_key))
            return

        st.session_state["tracked_appointment_id"] = str(appointment_id)
        result = triage(symptoms)
        st.success(
            t(
                "booking_confirmation",
                id=appointment_id,
                doctor=doctor["name"],
                time=chosen_row["display"],
                wait=chosen_row["wait"],
                min_unit=t("min_unit"),
            )
        )
        if result["level"] == "emergency":
            st.error(t("emergency_alert"))

    st.caption(t("disclaimer"))


def _render_my_appointment_tab():
    st.subheader(t("appointment_heading"))
    st.caption(t("appointment_caption"))

    if "tracked_appointment_id" not in st.session_state:
        st.session_state.tracked_appointment_id = ""

    # Keep the typed ID across auto-refresh by binding the widget to session_state.
    st.text_input(t("appointment_id"), key="tracked_appointment_id")
    raw_id = (st.session_state.tracked_appointment_id or "").strip()

    if raw_id:
        st_autorefresh(interval=5000, key="my_appt_refresh")

    if not raw_id:
        st.info(t("appointment_id_info"))
        return

    try:
        int(raw_id)
    except ValueError:
        st.error(t("appointment_id_number"))
        return

    status = get_appointment_status(raw_id)
    if status["status"] == "not_found":
        st.error(t("appointment_not_found"))
        return

    if status["status"] == "cancelled":
        st.warning(t("appointment_cancelled"))
        return
    if status["status"] == "seen":
        st.success(t("appointment_seen"))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("metric_position"), status["position"] or "—")
    c2.metric(t("metric_base_wait"), f"{status['base_wait']} {t('min_unit')}")
    c3.metric(t("metric_emergency_delay"), f"{status['delay']} {t('min_unit')}")
    c4.metric(t("metric_total_wait"), f"{status['total_wait']} {t('min_unit')}")

    triage_key = {
        "emergency": "triage_emergency",
        "urgent": "triage_urgent",
        "routine": "triage_routine",
    }[status["triage_level"]]

    st.caption(
        t(
            "triage_status",
            level=t(triage_key),
            emergency_ahead=t("yes" if status["emergency_active"] else "no"),
        )
    )

    if status["delay"] > 0:
        st.warning(
            t(
                "appointment_delay_warning",
                delay=status["delay"],
                min_unit=t("min_unit"),
            )
        )

    if st.button(t("cancel_button"), key="cancel_appt"):
        cancel_booking(raw_id)
        st.success(t("appointment_cancelled_success"))
        st.rerun()
