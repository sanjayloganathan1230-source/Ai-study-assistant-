"""Reusable UI pieces (headers, cards, chips, empty states)."""

from __future__ import annotations

import html

import streamlit as st

from src import config


def esc(value) -> str:
    """Escape text before putting it inside HTML. PDF text is untrusted, so ALWAYS use this."""
    return html.escape(str(value), quote=True)


def chip(text: str, kind: str = "") -> str:
    return f'<span class="chip {kind}">{esc(text)}</span>'


def page_header(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-header"><h1>{icon} {esc(title)}</h1><p>{esc(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def goto(page: str) -> None:
    """Button callback: switch page. (Callbacks run before the page is drawn, so this is safe.)"""
    st.session_state["nav"] = page


def empty_state(emoji: str, title: str, message: str, button_label: str | None = None,
                target: str | None = None, key: str | None = None) -> None:
    st.markdown(
        f'<div class="card empty"><div class="emoji">{emoji}</div>'
        f'<div class="card-title">{esc(title)}</div><div class="card-muted">{esc(message)}</div></div>',
        unsafe_allow_html=True,
    )
    if button_label and target:
        st.button(button_label, on_click=goto, args=(target,), key=key or f"goto_{target}", type="primary")


def require_document(feature: str):
    """Return the loaded document, or show a friendly prompt and return None."""
    doc = st.session_state.get("doc")
    if doc is None:
        empty_state(
            "📄", "No document loaded yet",
            f"Upload a PDF (or try the sample notes) to start using {feature}.",
            button_label="Go to Documents", target="Documents", key=f"need_doc_{feature}",
        )
    return doc


def ai_ready(show_notice: bool = True) -> bool:
    """True when an API key is configured. Otherwise explain clearly why AI buttons are off."""
    if config.api_key_available():
        return True
    if show_notice:
        st.warning(
            "**AI features are turned off** because no API key was found. "
            "Copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`, then restart the app. "
            "Uploading, searching your notes and study history still work."
        )
    return False


def source_card(page: int, score: float, text: str) -> None:
    st.markdown(
        f'<div class="source"><div class="source-head">Page {int(page)} · relevance {score:.2f}</div>'
        f'<div class="source-text">{esc(text)}</div></div>',
        unsafe_allow_html=True,
    )
