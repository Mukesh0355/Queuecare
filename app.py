"""
QueueCare — patient-first clinic queue and appointment prototype.

Run from the project folder:
    streamlit run app.py
"""

from pathlib import Path
import sys

# Make `logic` and `model` importable even if the working directory differs.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from logic.database import init_db, load_demo_data, reset_database
from logic.i18n import LANGUAGES, t
from logic.mobile import inject_mobile_css
from model.predict import reset_model_cache
from pages.doctor import render_doctor
from pages.patient import render_patient
from pages.performance import render_performance

MODEL_PKL = ROOT / "model" / "wait_model.pkl"
METRICS_JSON = ROOT / "model" / "metrics.json"


def ensure_ready():
    """Create the SQLite DB and train the wait model if they are missing."""
    init_db()
    if MODEL_PKL.exists() and METRICS_JSON.exists():
        return
    from model.generate_data import generate_data
    from model.train import train_model

    with st.spinner("First launch: generating clinic history and training the wait model…"):
        generate_data()
        train_model()
        reset_model_cache()


def _save_language():
    st.session_state["lang"] = LANGUAGES[st.session_state["lang_label"]]


st.set_page_config(
    page_title="QueueCare",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_mobile_css()
ensure_ready()

if "lang_label" not in st.session_state:
    st.session_state["lang_label"] = {
        language: label for label, language in LANGUAGES.items()
    }.get(st.session_state.get("lang", "en"), "English")
if "lang" not in st.session_state:
    st.session_state["lang"] = LANGUAGES[st.session_state["lang_label"]]

st.selectbox(
    t("language_label"),
    list(LANGUAGES),
    key="lang_label",
    on_change=_save_language,
    width=230,
)
st.session_state["lang"] = LANGUAGES[st.session_state["lang_label"]]

st.title("QueueCare")
st.markdown("**Know your wait, skip the crowd, and never delay an emergency.**")

with st.sidebar:
    st.header("QueueCare")
    view = st.radio(
        "Go to",
        ["Patient", "Doctor", "Model Performance"],
        key="main_nav",
    )
    st.divider()
    if st.button("Load demo data", key="load_demo"):
        try:
            ids = load_demo_data()
            st.success(
                "Loaded 5 sample patients for Doctor 1 "
                "(four routine + one chest-pain emergency). "
                f"Appointment IDs: {', '.join(str(i) for i in ids)}"
            )
            st.caption("Open the Doctor view (Dr. Mehta) to see the red emergency banner.")
        except ValueError as exc:
            st.error(str(exc))
    if st.button("Reset demo", key="reset_demo"):
        reset_database()
        st.success("Database reset. Doctors are ready; the queue is empty.")
    st.caption(
        "Demo clinic · 3 doctors · slots every 15 min from 9 AM to 5 PM. "
        "Triage is keyword support only — not a diagnosis."
    )

if view == "Patient":
    with st.container(key="patient_view_container"):
        render_patient()
elif view == "Doctor":
    render_doctor()
else:
    render_performance()
