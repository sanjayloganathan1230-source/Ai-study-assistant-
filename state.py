"""Session state: what the app remembers while you use it.

Streamlit re-runs the whole script after every click. `st.session_state` is the
dictionary that survives those re-runs. Everything here lives only in memory for
the current browser session. Nothing is written to disk except the small SQLite
records described in the README.
"""

from __future__ import annotations

import copy

import streamlit as st

DEFAULTS = {
    "nav": "Documents",    # which page is open
    "doc": None,           # the LoadedDocument being studied
    "chat": [],            # question/answer messages
    "summary": None,       # last generated summary
    "quiz": None,          # current quiz and its results
    "quiz_counter": 0,     # makes every quiz's widget keys unique
    "cards": None,         # current flashcard deck and position
}

STUDY_KEYS = ("chat", "summary", "quiz", "cards")


def init_state() -> None:
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)


def reset_study_state() -> None:
    """Forget generated study material (used when the document changes)."""
    for key in STUDY_KEYS:
        st.session_state[key] = copy.deepcopy(DEFAULTS[key])


def set_document(loaded) -> None:
    st.session_state["doc"] = loaded
    reset_study_state()


def close_document() -> None:
    """Button callback: remove the document (and its study material) from memory."""
    st.session_state["doc"] = None
    reset_study_state()
