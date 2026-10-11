"""
Load the trained wait model once and expose predict_wait().

If wait_model.pkl is missing, fall back to a simple rule:
    queue_length * that doctor's average consult minutes.
"""

from pathlib import Path

import joblib
import pandas as pd

# Same averages as generate_data.py / the doctors table
DOCTOR_AVG_CONSULT = {
    1: 10,
    2: 15,
    3: 12,
}

_MODEL = None
_MODEL_CHECKED = False


def _model_path() -> Path:
    return Path(__file__).resolve().parent / "wait_model.pkl"


def reset_model_cache():
    """Forget a loaded (or missing) model so the next call re-reads the pickle."""
    global _MODEL, _MODEL_CHECKED
    _MODEL = None
    _MODEL_CHECKED = False


def _load_model():
    """Load the pickle once per process. Returns None if the file is absent."""
    global _MODEL, _MODEL_CHECKED
    if _MODEL_CHECKED:
        return _MODEL
    _MODEL_CHECKED = True
    path = _model_path()
    if path.exists():
        _MODEL = joblib.load(path)
    else:
        _MODEL = None
    return _MODEL


def predict_wait(doctor_id, hour, day_of_week, queue_length) -> int:
    """
    Predict waiting-room minutes for a patient joining this doctor's queue.

    Returns a non-negative integer number of minutes.
    """
    doctor_id = int(doctor_id)
    hour = int(hour)
    day_of_week = int(day_of_week)
    queue_length = int(max(0, queue_length))
    avg_consult_min = DOCTOR_AVG_CONSULT.get(doctor_id, 12)

    # Nobody ahead means you are next — don't let model noise invent a wait.
    if queue_length <= 0:
        return 0

    model = _load_model()
    if model is None:
        # Rule-of-thumb fallback when the model has not been trained yet
        return int(queue_length * avg_consult_min)

    features = pd.DataFrame(
        [
            {
                "doctor_id": doctor_id,
                "hour": hour,
                "day_of_week": day_of_week,
                "queue_length": queue_length,
                "avg_consult_min": avg_consult_min,
            }
        ]
    )
    pred = float(model.predict(features)[0])
    return int(max(0, round(pred)))
