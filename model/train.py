"""
Train a Gradient Boosting model that predicts waiting-room minutes.

Saves:
  model/wait_model.pkl     – trained regressor
  model/metrics.json       – MAE vs naive baseline MAE
  model/test_results.csv   – predicted vs actual on the hold-out set
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

try:
    from generate_data import generate_data  # python model/train.py
except ImportError:
    from model.generate_data import generate_data  # imported by app.py

FEATURE_COLS = [
    "doctor_id",
    "hour",
    "day_of_week",
    "queue_length",
    "avg_consult_min",
]
TARGET_COL = "wait_minutes"
RANDOM_SEED = 42


def _model_dir() -> Path:
    return Path(__file__).resolve().parent


def train_model() -> dict:
    """Fit the wait model, write artifacts, and return the metrics dict."""
    model_dir = _model_dir()
    data_path = model_dir / "data.csv"
    if not data_path.exists():
        generate_data()

    df = pd.read_csv(data_path)
    X = df[FEATURE_COLS]
    y = df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED
    )

    model = GradientBoostingRegressor(random_state=RANDOM_SEED)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred))

    # Naive baseline: always guess the training-set mean wait
    baseline_pred = np.full(shape=len(y_test), fill_value=float(y_train.mean()))
    baseline_mae = float(mean_absolute_error(y_test, baseline_pred))

    joblib.dump(model, model_dir / "wait_model.pkl")

    metrics = {
        "mae": round(mae, 3),
        "baseline_mae": round(baseline_mae, 3),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
    }
    with open(model_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    results = pd.DataFrame(
        {
            "actual": y_test.reset_index(drop=True),
            "predicted": np.round(y_pred, 2),
        }
    )
    results.to_csv(model_dir / "test_results.csv", index=False)
    return metrics


if __name__ == "__main__":
    metrics = train_model()
    print("Training complete.")
    print(f"  MAE:          {metrics['mae']} min")
    print(f"  Baseline MAE: {metrics['baseline_mae']} min")
