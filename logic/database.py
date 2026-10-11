"""
SQLite helpers for doctors, patients, and the live clinic queue.

queuecare.db is created automatically on first run, with 3 doctors seeded.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from logic.triage import triage

# Extra wait added for each waiting emergency (times the doctor's average consult).
# Example: GP avg 10 min -> round(1.5 * 10) = 15 extra minutes per emergency.
EMERGENCY_DELAY_MULTIPLIER = 1.5

# Database lives in the project root so `streamlit run app.py` just works.
DB_PATH = Path(__file__).resolve().parent.parent / "queuecare.db"

DOCTORS = [
    (1, "Dr. Mehta", "General Physician", 10),
    (2, "Dr. Sharma", "Cardiologist", 15),
    (3, "Dr. Rao", "Pediatrician", 12),
]

# Clinic hours: 9:00 to 17:00, a new slot every 15 minutes (last start 16:45).
SLOT_START_HOUR = 9
SLOT_END_HOUR = 17
SLOT_MINUTES = 15


def get_connection():
    """Open a SQLite connection. row_factory makes rows dict-like."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables and seed the 3 doctors on first run."""
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                avg_consult_min INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                slot_time TEXT NOT NULL,
                symptoms TEXT,
                triage_level TEXT NOT NULL,
                matched_keyword TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (doctor_id) REFERENCES doctors(id)
            );
            """
        )
        existing = conn.execute("SELECT COUNT(*) AS n FROM doctors").fetchone()["n"]
        if existing == 0:
            conn.executemany(
                "INSERT INTO doctors (id, name, specialty, avg_consult_min) VALUES (?, ?, ?, ?)",
                DOCTORS,
            )
        conn.commit()
    finally:
        conn.close()


def reset_database():
    """Wipe patients and appointments, then re-seed doctors. Used by Reset demo."""
    conn = get_connection()
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS appointments;
            DROP TABLE IF EXISTS patients;
            DROP TABLE IF EXISTS doctors;
            """
        )
        conn.commit()
    finally:
        conn.close()
    init_db()


def get_doctors():
    """Return all doctors as a list of dicts."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, specialty, avg_consult_min FROM doctors ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_doctor(doctor_id):
    """Return one doctor dict, or None."""
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, specialty, avg_consult_min FROM doctors WHERE id = ?",
            (int(doctor_id),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def generate_slots(for_date=None):
    """Build today's 15-minute slot labels, e.g. '2026-10-10 09:00'."""
    day = (for_date or datetime.now().date()).isoformat()
    slots = []
    minutes_from_open = 0
    total_minutes = (SLOT_END_HOUR - SLOT_START_HOUR) * 60
    while minutes_from_open < total_minutes:
        hour = SLOT_START_HOUR + minutes_from_open // 60
        minute = minutes_from_open % 60
        slots.append(f"{day} {hour:02d}:{minute:02d}")
        minutes_from_open += SLOT_MINUTES
    return slots


def _is_slot_taken(conn, doctor_id, slot_time):
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM appointments
        WHERE doctor_id = ? AND slot_time = ? AND status = 'waiting'
        """,
        (int(doctor_id), slot_time),
    ).fetchone()
    return row["n"] > 0


def get_taken_slots(doctor_id):
    """Set of waiting slot_time strings for this doctor."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT slot_time FROM appointments
            WHERE doctor_id = ? AND status = 'waiting'
            """,
            (int(doctor_id),),
        ).fetchall()
        return {r["slot_time"] for r in rows}
    finally:
        conn.close()


def patients_ahead(doctor_id, slot_time) -> int:
    """How many waiting patients are booked at or before this slot today."""
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM appointments
            WHERE doctor_id = ?
              AND status = 'waiting'
              AND slot_time <= ?
            """,
            (int(doctor_id), slot_time),
        ).fetchone()
        return int(row["n"])
    finally:
        conn.close()


def book_slot(patient_name, age, doctor_id, slot_time, symptoms) -> int:
    """
    Register the patient, run triage, and insert a waiting appointment.

    Returns the new appointment_id.
    """
    init_db()
    name = (patient_name or "").strip()
    if not name:
        raise ValueError("Patient name is required.")
    if age is None or int(age) < 0:
        raise ValueError("A valid age is required.")
    if not slot_time:
        raise ValueError("A time slot is required.")

    flags = triage(symptoms)
    now = datetime.now().isoformat(timespec="seconds")

    conn = get_connection()
    try:
        if _is_slot_taken(conn, doctor_id, slot_time):
            raise ValueError("That slot is already booked. Please pick another.")

        cur = conn.execute(
            "INSERT INTO patients (name, age) VALUES (?, ?)",
            (name, int(age)),
        )
        patient_id = cur.lastrowid
        cur = conn.execute(
            """
            INSERT INTO appointments (
                patient_id, doctor_id, slot_time, symptoms,
                triage_level, matched_keyword, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'waiting', ?)
            """,
            (
                patient_id,
                int(doctor_id),
                slot_time,
                symptoms or "",
                flags["level"],
                flags["matched"],
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_queue(doctor_id) -> list:
    """
    Waiting patients for this doctor.

    Sort: emergency, then urgent, then routine, then by slot_time.
    """
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                a.id AS appointment_id,
                p.name AS patient_name,
                p.age AS age,
                a.doctor_id AS doctor_id,
                a.slot_time AS slot_time,
                a.symptoms AS symptoms,
                a.triage_level AS triage_level,
                a.matched_keyword AS matched_keyword,
                a.status AS status,
                a.created_at AS created_at
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            WHERE a.doctor_id = ? AND a.status = 'waiting'
            ORDER BY
                CASE a.triage_level
                    WHEN 'emergency' THEN 0
                    WHEN 'urgent' THEN 1
                    ELSE 2
                END,
                a.slot_time ASC
            """,
            (int(doctor_id),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_emergency_delay(doctor_id) -> int:
    """
    Extra minutes caused by waiting emergency patients for this doctor.

    delay = (count of waiting emergencies)
            * round(EMERGENCY_DELAY_MULTIPLIER * doctor's avg_consult_min)
    """
    doctor = get_doctor(doctor_id)
    if not doctor:
        return 0
    queue = get_queue(doctor_id)
    n_emergency = sum(1 for p in queue if p["triage_level"] == "emergency")
    extra_each = int(round(EMERGENCY_DELAY_MULTIPLIER * doctor["avg_consult_min"]))
    return n_emergency * extra_each


def _get_appointment_row(appointment_id):
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                a.id AS appointment_id,
                p.name AS patient_name,
                p.age AS age,
                a.doctor_id AS doctor_id,
                a.slot_time AS slot_time,
                a.symptoms AS symptoms,
                a.triage_level AS triage_level,
                a.matched_keyword AS matched_keyword,
                a.status AS status
            FROM appointments a
            JOIN patients p ON p.id = a.patient_id
            WHERE a.id = ?
            """,
            (int(appointment_id),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_appointment_status(appointment_id) -> dict:
    """
    Live status for My Appointment.

    position: 1 = next in the triage-sorted queue
    base_wait: model prediction using position as queue_length
    delay: emergency extra minutes, 0 if this patient is an emergency
    total_wait: base_wait + delay
    """
    not_found = {
        "position": None,
        "base_wait": 0,
        "delay": 0,
        "total_wait": 0,
        "emergency_active": False,
        "triage_level": None,
        "status": "not_found",
    }
    try:
        appt_id = int(appointment_id)
    except (TypeError, ValueError):
        return not_found

    row = _get_appointment_row(appt_id)
    if not row:
        return not_found

    # Import here to keep database.py usable even before the model is trained.
    from model.predict import predict_wait

    doctor_id = row["doctor_id"]
    queue = get_queue(doctor_id)
    emergency_active = any(p["triage_level"] == "emergency" for p in queue)
    delay_total = get_emergency_delay(doctor_id)

    position = None
    for i, person in enumerate(queue, start=1):
        if person["appointment_id"] == appt_id:
            position = i
            break

    now = datetime.now()
    if row["status"] != "waiting" or position is None:
        return {
            "position": position,
            "base_wait": 0,
            "delay": 0,
            "total_wait": 0,
            "emergency_active": emergency_active,
            "triage_level": row["triage_level"],
            "status": row["status"],
        }

    base_wait = predict_wait(doctor_id, now.hour, now.weekday(), position)
    # Emergency patients are seen first, so they do not pay the delay they cause.
    delay = 0 if row["triage_level"] == "emergency" else delay_total
    return {
        "position": position,
        "base_wait": int(base_wait),
        "delay": int(delay),
        "total_wait": int(base_wait) + int(delay),
        "emergency_active": emergency_active,
        "triage_level": row["triage_level"],
        "status": row["status"],
    }


def cancel_booking(appointment_id):
    """Mark an appointment cancelled so the slot can be reused."""
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
            (int(appointment_id),),
        )
        conn.commit()
    finally:
        conn.close()


def complete_visit(appointment_id):
    """Mark an appointment as seen (doctor finished the consult)."""
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE appointments SET status = 'seen' WHERE id = ?",
            (int(appointment_id),),
        )
        conn.commit()
    finally:
        conn.close()


def load_demo_data() -> list:
    """
    Book 5 sample patients for Doctor 1: four routine + one chest-pain emergency.

    Returns the list of new appointment ids.
    """
    init_db()
    slots = [s for s in generate_slots() if s not in get_taken_slots(1)]
    samples = [
        ("Rahul Verma", 31, "mild cough and cold"),
        ("Priya Nair", 27, "routine checkup"),
        ("Anita Kapoor", 54, "sudden chest pain and sweating"),
        ("Vikram Joshi", 44, "blood pressure follow up"),
        ("Meera Iyer", 36, "skin rash"),
    ]
    if len(slots) < len(samples):
        raise ValueError("Not enough free slots. Click Reset demo, then Load demo data.")

    ids = []
    for i, (name, age, symptoms) in enumerate(samples):
        ids.append(book_slot(name, age, 1, slots[i], symptoms))
    return ids
