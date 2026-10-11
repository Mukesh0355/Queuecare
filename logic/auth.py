"""Session-backed doctor PIN authentication."""

import hmac
from collections.abc import Mapping

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


DEMO_PINS = {"1": "1111", "2": "2222", "3": "3333"}


def _read_pins() -> tuple[dict[str, str], bool]:
    try:
        configured_pins = st.secrets["doctor_pins"]
    except (KeyError, StreamlitSecretNotFoundError):
        return DEMO_PINS.copy(), True

    if not isinstance(configured_pins, Mapping):
        raise ValueError("The doctor_pins secret must be a mapping of doctor IDs to PINs.")

    pins = {str(doctor_id): str(pin) for doctor_id, pin in configured_pins.items()}
    if not pins or any(not doctor_id or not pin for doctor_id, pin in pins.items()):
        raise ValueError("The doctor_pins secret must contain doctor IDs and non-empty PINs.")
    return pins, False


def get_pins() -> dict[str, str]:
    """Read configured doctor PINs, or display a warning and use demo PINs."""
    pins, using_demo_pins = _read_pins()
    if using_demo_pins:
        st.caption("Demo PINs in use. Set .streamlit/secrets.toml for real use.")
    return pins


def login(doctor_id, pin) -> bool:
    """Validate a doctor's PIN using a constant-time comparison."""
    pins, _ = _read_pins()
    expected_pin = pins.get(str(doctor_id))
    provided_pin = str(pin).encode("utf-8")
    expected_bytes = (expected_pin or "").encode("utf-8")
    return expected_pin is not None and hmac.compare_digest(
        expected_bytes, provided_pin
    )


def current_doctor_id():
    """Return the doctor ID authenticated in this Streamlit session."""
    return st.session_state.get("auth_doctor_id")


def logout():
    """Clear the authenticated doctor from this Streamlit session."""
    st.session_state.pop("auth_doctor_id", None)
