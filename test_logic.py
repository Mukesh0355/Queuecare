"""
Logic check for judges / teammates.

Books 5 patients for Doctor 1, including one "chest pain" emergency.
Prints the queue order and the emergency delay, then confirms the
emergency is first.
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from logic.database import (
    book_slot,
    get_appointment_status,
    get_emergency_delay,
    get_queue,
    reset_database,
)
from logic.triage import triage


def main():
    reset_database()
    today = datetime.now().date().isoformat()

    patients = [
        ("Ravi Kumar", 40, 1, f"{today} 09:00", "mild headache"),
        ("Sana Ali", 29, 1, f"{today} 09:15", "routine checkup"),
        ("Amit Shah", 55, 1, f"{today} 09:30", "chest pain"),
        ("Neha Gupta", 33, 1, f"{today} 09:45", "cold and cough"),
        ("Omar Khan", 47, 1, f"{today} 10:00", "follow up visit"),
    ]

    ids = []
    print("Bookings:")
    for name, age, doctor_id, slot, symptoms in patients:
        flags = triage(symptoms)
        appt_id = book_slot(name, age, doctor_id, slot, symptoms)
        ids.append(appt_id)
        print(
            f"  id={appt_id}  {name:12}  triage={flags['level']:9}  "
            f"matched={flags['matched']}"
        )

    queue = get_queue(1)
    print("\nQueue order for Doctor 1 (emergency, urgent, routine, then slot):")
    for i, row in enumerate(queue, start=1):
        print(
            f"  {i}. {row['patient_name']:12}  [{row['triage_level']}]  "
            f"slot={row['slot_time']}"
        )

    delay = get_emergency_delay(1)
    print(f"\nEmergency delay for other patients: {delay} min")

    assert queue, "Queue should not be empty"
    assert queue[0]["triage_level"] == "emergency", "Emergency should be first"
    assert queue[0]["patient_name"] == "Amit Shah", "Chest-pain patient should be first"
    print("PASS: emergency patient is first in the queue.")

    routine_status = get_appointment_status(ids[0])
    print(f"Routine patient (id={ids[0]}) status: {routine_status}")
    assert routine_status["delay"] > 0, "Routine patients should see extra delay"
    print("PASS: routine patient wait includes emergency delay.")

    emergency_status = get_appointment_status(ids[2])
    print(f"Emergency patient (id={ids[2]}) status: {emergency_status}")
    assert emergency_status["delay"] == 0, "Emergency patients should have delay 0"
    assert emergency_status["position"] == 1, "Emergency should be position 1"
    print("PASS: emergency patient has delay 0 and position 1.")


if __name__ == "__main__":
    main()
