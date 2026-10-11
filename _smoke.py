"""Temporary smoke test — delete after running."""
from logic.triage import triage
from logic.database import (
    init_db,
    reset_database,
    book_slot,
    get_queue,
    complete_visit,
    cancel_booking,
    load_demo_data,
    get_doctors,
)
from model.predict import predict_wait

assert triage("sudden chest pain")["level"] == "emergency"
assert triage("can't breathe")["matched"] == "can't breathe"
assert triage("cannot breathe")["level"] == "emergency"
assert triage("high fever")["level"] == "urgent"
assert triage("mild cough")["level"] == "routine"
assert triage("heart attack and vomiting")["level"] == "emergency"

init_db()
reset_database()
docs = get_doctors()
assert [d["id"] for d in docs] == [1, 2, 3]
w = predict_wait(3, 11, 2, 3)
assert isinstance(w, int) and w >= 0
aid = book_slot("Test", 40, 1, "2026-10-10 09:00", "routine checkup")
assert isinstance(aid, int)
q = get_queue(1)
assert len(q) == 1
cancel_booking(aid)
assert get_queue(1) == []
ids = load_demo_data()
assert len(ids) == 5
q2 = get_queue(2)
assert q2[0]["triage_level"] == "emergency"
assert q2[0]["matched_keyword"] == "chest pain"
complete_visit(q2[0]["appointment_id"], q2[0]["doctor_id"])
assert get_queue(2) == []
print("SMOKE OK wait=", w)
