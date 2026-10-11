"""Small-screen styling for QueueCare."""

import streamlit as st


def inject_mobile_css():
    st.markdown(
        """
        <style>
        .st-key-patient_view_container {
            width: 100%;
            max-width: 720px;
            min-width: 0;
            margin-inline: auto;
        }
        div[data-testid="stElementContainer"]:has(> div[data-testid="stButton"]) {
            width: 100% !important;
        }
        div[data-testid="stButton"] {
            width: 100%;
        }
        div[data-testid="stButton"] > button {
            width: 100%;
            min-height: 48px;
            font-size: 18px;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextArea"] textarea {
            min-height: 48px;
            font-size: 16px;
        }
        div[data-testid="stTextArea"] textarea {
            min-height: 112px;
        }
        div[data-testid="stSelectbox"] [data-baseweb="select"],
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
        div[data-testid="stSelectbox"] input[role="combobox"] {
            min-height: 48px;
            font-size: 16px;
        }
        div[data-testid="stNumberInput"] button {
            min-width: 42px;
            min-height: 48px;
        }
        div[data-testid="stMetric"] {
            min-width: 0;
            padding: 12px;
            border: 1px solid rgba(128, 128, 128, 0.35);
            border-radius: 12px;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-size: 1.65rem;
        }
        .st-key-appointment_metrics [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap;
        }
        .st-key-appointment_metrics [data-testid="stColumn"] {
            min-width: 0;
            flex: 1 1 0%;
        }
        div[data-testid="stTabs"] [role="tablist"] {
            max-width: 100%;
            flex-wrap: nowrap;
            overflow-x: auto;
            scrollbar-width: none;
        }
        div[data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar {
            display: none;
        }
        div[data-testid="stTabs"] [role="tab"] {
            min-height: 48px;
            flex: 0 0 auto;
            padding: 12px 16px;
            font-size: 16px;
            white-space: nowrap;
        }
        .st-key-book_slot [role="radiogroup"],
        .st-key-book_slot_afternoon [role="radiogroup"] {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
        }
        .st-key-book_slot button[data-variant="pills"],
        .st-key-book_slot_afternoon button[data-variant="pills"] {
            width: 100%;
            min-width: 0;
            min-height: 48px;
            height: auto;
            padding: 8px 12px;
            font-size: 16px;
            white-space: normal;
        }
        div[data-testid="stAlert"] {
            border: 2px solid currentColor;
            font-weight: 600;
        }
        .queuecare-total-wait {
            margin: 8px 0 12px;
            padding: 20px;
            border: 2px solid var(--wait-border);
            border-radius: 16px;
            background: var(--wait-background);
            color: var(--wait-text);
        }
        .queuecare-total-wait-label {
            display: block;
            font-size: 1rem;
            font-weight: 600;
        }
        .queuecare-total-wait-value {
            display: block;
            margin-top: 4px;
            font-size: 2.25rem;
            font-weight: 750;
            line-height: 1.2;
        }
        @media (max-width: 640px) {
            div[data-testid="stMainBlockContainer"] {
                padding: 1rem 0.75rem 2rem;
            }
            .st-key-patient_view_container {
                max-width: 100%;
            }
            div[data-testid="stMetric"] {
                padding: 10px;
            }
            .queuecare-total-wait {
                padding: 16px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
