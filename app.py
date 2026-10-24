"""AI Study Assistant: the app you run.

    streamlit run app.py

This file only does three things: set up the page, draw the sidebar, and show
whichever page the student picked. All the real work lives in the `src` folder.
"""

import streamlit as st

from src import config
from src import database as db
from src.ui import state
from src.ui.components import chip, esc
from src.ui.formatting import STATUS_LABELS
from src.ui.pages import NAV_ICONS, PAGES
from src.ui.styles import inject_css

st.set_page_config(page_title=config.APP_NAME, page_icon="🎓", layout="wide", initial_sidebar_state="expanded")


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="brand"><div class="brand-logo">🎓</div><div><div class="brand-name">Study Assistant</div>'
            '<div class="brand-sub">Learn from your own notes</div></div></div>',
            unsafe_allow_html=True,
        )
        st.radio("Go to", list(PAGES), key="nav", format_func=lambda p: f"{NAV_ICONS[p]}  {p}",
                 label_visibility="collapsed")
        st.divider()

        doc = st.session_state.get("doc")
        if doc is None:
            st.caption("No document loaded")
        else:
            kind = "ok" if doc.status == "ready" else "warn"
            st.markdown(
                f'<div class="card"><div class="card-title">📄 {esc(doc.name)}</div>'
                f'<div class="card-muted">{doc.page_count} pages · {len(doc.chunks)} chunks</div>'
                f'{chip(STATUS_LABELS.get(doc.status, doc.status), kind)}</div>',
                unsafe_allow_html=True,
            )
            st.button("✖️ Close document", on_click=state.close_document, key="close_doc_btn")

        if config.api_key_available():
            st.markdown(chip("AI: API key found", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(chip("AI: off (no API key)", "off"), unsafe_allow_html=True)
        st.caption(f"Model: {config.LLM_MODEL}")


def main() -> None:
    inject_css()
    state.init_state()
    try:
        db.init_db()
    except Exception:
        st.error("The study database could not be opened. Check that the `data/` folder is writable.")
        st.stop()
    render_sidebar()
    PAGES[st.session_state["nav"]]()


main()
