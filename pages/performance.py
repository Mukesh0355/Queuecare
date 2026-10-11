"""Show how the wait model compares with a naive mean baseline."""

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
METRICS_PATH = MODEL_DIR / "metrics.json"
RESULTS_PATH = MODEL_DIR / "test_results.csv"


def render_performance():
    st.subheader("Model performance")
    st.caption(
        "Gradient Boosting wait predictor vs a naive baseline that always guesses "
        "the average wait from the training data."
    )

    if not METRICS_PATH.exists() or not RESULTS_PATH.exists():
        st.warning(
            "Metrics not found yet. The app trains the model on first launch. "
            "If you still see this, run `python model/generate_data.py` then "
            "`python model/train.py`."
        )
        return

    with open(METRICS_PATH, encoding="utf-8") as f:
        metrics = json.load(f)

    mae = float(metrics.get("mae", 0))
    baseline = float(metrics.get("baseline_mae", 0))
    improvement = baseline - mae

    c1, c2, c3 = st.columns(3)
    c1.metric("Model MAE (minutes)", f"{mae:.2f}")
    c2.metric("Baseline MAE (minutes)", f"{baseline:.2f}")
    c3.metric("Improvement", f"{improvement:.2f}", delta=f"{improvement:.2f} min better")

    st.write(
        f"Trained on **{metrics.get('n_train', '—')}** visits, "
        f"tested on **{metrics.get('n_test', '—')}**. "
        "Lower MAE is better: the model is closer to the true wait than guessing the mean."
    )

    results = pd.read_csv(RESULTS_PATH)
    max_val = float(max(results["actual"].max(), results["predicted"].max()))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=results["actual"],
            y=results["predicted"],
            mode="markers",
            name="Test visits",
            marker=dict(size=7, opacity=0.55),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode="lines",
            name="Perfect prediction",
            line=dict(dash="dash"),
        )
    )
    fig.update_layout(
        title="Predicted vs actual wait (test set)",
        xaxis_title="Actual wait (minutes)",
        yaxis_title="Predicted wait (minutes)",
        height=480,
    )
    st.plotly_chart(fig, use_container_width=True)
