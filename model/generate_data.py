"""
Generate synthetic historical visit data for wait-time training.

Wait time is roughly: patients ahead * typical consult length, plus
random noise and extra delay during peak clinic hours (10–12 and 16–17).
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Clinic doctors: id -> average consult minutes (must match the live clinic).
DOCTOR_AVG_CONSULT = {
    1: 10,  # General Physician
    2: 15,  # Cardiologist
    3: 12,  # Pediatrician
}

PEAK_HOURS = {10, 11, 12, 16, 17}
N_ROWS = 2000
RANDOM_SEED = 42


def _data_path() -> Path:
    """Save data.csv next to this file so paths stay relative and portable."""
    return Path(__file__).resolve().parent / "data.csv"


def generate_data(n_rows: int = N_ROWS, seed: int = RANDOM_SEED) -> Path:
    """Create n_rows of synthetic visits and write model/data.csv."""
    rng = np.random.default_rng(seed)
    doctor_ids = np.array(list(DOCTOR_AVG_CONSULT.keys()))

    rows = []
    for _ in range(n_rows):
        doctor_id = int(rng.choice(doctor_ids))
        hour = int(rng.integers(9, 18))  # 9 AM through 5 PM (hour 17)
        day_of_week = int(rng.integers(0, 7))  # 0 = Monday ... 6 = Sunday
        queue_length = int(rng.integers(0, 13))
        avg_consult_min = DOCTOR_AVG_CONSULT[doctor_id]

        # Base wait: everyone ahead of you takes about avg_consult_min
        wait = queue_length * avg_consult_min
        wait += float(rng.normal(0, 4))  # everyday variation

        # Peak hours: extra delay from crowding / late consults
        if hour in PEAK_HOURS:
            wait += float(rng.uniform(5, 15))

        wait_minutes = int(max(0, round(wait)))
        rows.append(
            {
                "doctor_id": doctor_id,
                "hour": hour,
                "day_of_week": day_of_week,
                "queue_length": queue_length,
                "avg_consult_min": avg_consult_min,
                "wait_minutes": wait_minutes,
            }
        )

    out_path = _data_path()
    pd.DataFrame(rows).to_csv(out_path, index=False)
    return out_path


if __name__ == "__main__":
    path = generate_data()
    print(f"Wrote {N_ROWS} synthetic visits to {path}")
