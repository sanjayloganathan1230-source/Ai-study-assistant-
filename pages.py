"""The six dashboard pages. Each `render_*` function draws one page.

Pattern used on every page:
    1. make sure a document is loaded (require_document)
    2. read what the student did (buttons, text boxes)
    3. call the logic modules (retrieval / ai_service / database)
    4. show the result, or a friendly error
"""

from __future__ import annotations

import random

import streamlit as st

from src import config
from src import database as db
from src.ai_service import AIServiceError, StudyAI, get_client
from src.document_loader import load_pdf_bytes, load_sample_notes
from src.pdf_processor import PDFError
from src.ui import state
from src.ui.components import (
    ai_ready,
    chip,
    empty_state,
    esc,
    page_header,
    require_document,
    source_card,
)
from src.ui.formatting import (
    ACTIVITY_LABELS,
    STATUS_LABELS,
    document_rows,
    format_number,
    history_rows,
    score_message,
    truncate,
)
from src.validators import score_answers

NO_AI_SEARCH_NOTE = "AI is off, so this shows the most relevant passages from your notes instead of an answer."


# ------------------------------------------------------------------ shared helpers
def _get_ai():
    """Return (StudyAI, None) or (None, friendly_error_message)."""
    try:
        return StudyAI(get_client()), None
    except AIServiceError as exc:
        return None, str(exc)


def _save_history(*args, **kwargs) -> None:
    """History is a nice-to-have: a database problem must never break studying."""
    try:
        db.add_history(*args, **kwargs)
    except Exception:
        st.toast("Could not save to study history.", icon="⚠️")


def _load_into_session(loader) -> None:
    """Run a document loader with a spinner and show friendly errors."""
    try:
        with st.spinner("Reading your document…"):
            loaded = loader()
    except PDFError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("Something unexpected went wrong while reading this file. Please try another PDF.")
        return
    state.set_document(loaded)
    st.rerun()


# ======================================================================= Documents
def render_documents() -> None:
    st.markdown(
        '<div class="hero"><h1>🎓 AI Study Assistant</h1>'
        "<p>Upload your PDF notes, then ask questions, get summaries, practise with quizzes and flashcards.</p></div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("Upload your notes")
        uploaded = st.file_uploader(
            "Choose a PDF file",
            type=["pdf"],
            help=f"Text-based PDFs only (not scans). Maximum {config.MAX_UPLOAD_MB} MB.",
            key="pdf_uploader",
        )
        c1, c2 = st.columns(2)
        process = c1.button("⚙️ Process PDF", type="primary", disabled=uploaded is None, key="process_btn")
        sample = c2.button("✨ Try sample notes", key="sample_btn")

        if process and uploaded is not None:
            _load_into_session(lambda: load_pdf_bytes(uploaded.getvalue(), uploaded.name))
        if sample:
            _load_into_session(load_sample_notes)

    with right:
        st.subheader("Current document")
        doc = st.session_state.get("doc")
        if doc is None:
            empty_state("📄", "Nothing loaded", "Process a PDF or try the sample notes to begin.")
        else:
            kind = "ok" if doc.status == "ready" else "warn"
            st.markdown(
                f'<div class="card"><div class="card-title">📄 {esc(doc.name)}</div>'
                f'{chip("✅ " + STATUS_LABELS.get(doc.status, doc.status), kind)}</div>',
                unsafe_allow_html=True,
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Pages", doc.page_count)
            m2.metric("Chunks", len(doc.chunks))
            m3.metric("Characters", format_number(doc.processed.total_chars))
            for warning in doc.warnings:
                st.warning(warning)
            if doc.previously_uploaded:
                st.info("You have uploaded this exact file before, so its saved record was reused.")

    st.divider()
    stats = db.get_stats()
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Documents", stats["documents"])
    s2.metric("Questions", stats["questions"])
    s3.metric("Summaries", stats["summaries"])
    s4.metric("Quizzes", stats["quizzes"])
    avg = stats["avg_quiz_percent"]
    s5.metric("Avg quiz score", "–" if avg is None else f"{avg:g}%")

    with st.expander("🔒 How is my data stored?"):
        st.markdown(
            f"""
- **Your PDF** is read into memory and **never saved to disk**. When you close the tab or press
  *Close document*, it is gone.
- **Extracted text and the search index** exist only in memory for the current session.
- **A small SQLite file** (`{config.DB_PATH.name}` in the `data/` folder) keeps only:
  file name, page count, chunk count, character count, a fingerprint (hash) of the file and the upload time,
  plus short **study history** entries (your question, a short preview of the result, quiz scores).
  It never contains the full text of your PDF.
- **AI requests:** when you use an AI feature, the *relevant excerpts* of your notes are sent to the
  Anthropic API to produce the answer. Do not upload documents you are not allowed to share.
- **Your API key** is read from the `.env` file / environment. It is never shown in this app and never saved
  in the database. You can wipe history on the *History* page.
"""
        )


# ======================================================================= Ask Questions
def _render_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
            return
        if msg.get("mode") == "search" and msg.get("sources"):
            st.info(NO_AI_SEARCH_NOTE)
        elif not msg.get("found", True):
            st.warning(msg["content"])
        else:
            st.markdown(msg["content"])
        sources = msg.get("sources") or []
        if sources:
            with st.expander(f"📚 Sources ({len(sources)})"):
                for src in sources:
                    source_card(src["page"], src["score"], truncate(src["text"], 600))


def _source_dicts(results) -> list[dict]:
    return [{"page": r.page_number, "score": round(r.score, 2), "text": r.text} for r in results]


def render_chat() -> None:
    page_header("💬", "Ask Questions", "Answers come only from your notes, with the pages they were found on.")
    doc = require_document("question answering")
    if doc is None:
        return
    ai_on = ai_ready()

    top = st.columns([4, 1])
    top[0].caption(f"Document: **{doc.name}** · {doc.page_count} pages")
    top[1].button("🧹 Clear chat", key="clear_chat", on_click=lambda: st.session_state.update(chat=[]))

    if not st.session_state["chat"]:
        st.markdown(
            '<div class="card card-muted">Try asking: <i>“What is overfitting?”</i> or '
            "<i>“Explain precision and recall.”</i></div>",
            unsafe_allow_html=True,
        )
    for msg in st.session_state["chat"]:
        _render_message(msg)

    question = st.chat_input("Ask a question about your notes…")
    if not question:
        return
    question = question.strip()[:1000]
    user_msg = {"role": "user", "content": question}
    with st.chat_message("user"):
        st.markdown(question)

    results = doc.store.search(question)

    if ai_on:
        study_ai, error = _get_ai()
        if study_ai is None:
            st.error(error)
            return
        try:
            with st.chat_message("assistant"):
                with st.spinner("Reading the relevant passages…"):
                    answer = study_ai.answer_question(question, results)
        except AIServiceError as exc:
            st.error(str(exc))
            return
        reply = {"role": "assistant", "content": answer.text, "found": answer.found, "mode": "ai",
                 "sources": _source_dicts(answer.sources)}
        preview = answer.text
    else:
        text = "No passages in your notes matched this question." if not results else NO_AI_SEARCH_NOTE
        reply = {"role": "assistant", "content": text, "found": bool(results), "mode": "search",
                 "sources": _source_dicts(results)}
        preview = "Search only: " + (f"{len(results)} passage(s) found" if results else "nothing found")

    st.session_state["chat"] += [user_msg, reply]
    _save_history("question", question, preview, document_id=doc.doc_id)
    st.rerun()


# ======================================================================= Summaries
def render_summaries() -> None:
    page_header("📝", "Smart Summaries", "Easy-to-read summaries built from your document text.")
    doc = require_document("summaries")
    if doc is None:
        return
    ai_on = ai_ready()

    with st.container(border=True):
        mode_label = st.radio(
            "Summary type",
            ["Short summary", "Detailed chapter summary"],
            horizontal=True,
            key="summary_mode",
            help="Short: the main ideas in about 150 words. Detailed: section-by-section notes with page ranges.",
        )
        generate = st.button("✨ Generate summary", type="primary", disabled=not ai_on, key="summary_btn")

    if generate and ai_on:
        study_ai, error = _get_ai()
        if study_ai is None:
            st.error(error)
        else:
            mode = "short" if mode_label.startswith("Short") else "detailed"
            try:
                with st.spinner("Writing your summary… detailed summaries can take a minute."):
                    summary = study_ai.summarize(doc.chunks, mode)
            except AIServiceError as exc:
                st.error(str(exc))
            else:
                st.session_state["summary"] = {"mode": mode, "text": summary.text, "partial": summary.partial,
                                               "doc": doc.name}
                _save_history("summary", f"{mode_label} of {doc.name}", summary.text, document_id=doc.doc_id)

    result = st.session_state.get("summary")
    if result:
        st.markdown(
            f'<div class="card"><div class="card-title">'
            f'{"Short summary" if result["mode"] == "short" else "Detailed summary"} · {esc(result["doc"])}'
            f"</div></div>",
            unsafe_allow_html=True,
        )
        if result["partial"]:
            st.warning("This document is long, so only part of it was used for this summary.")
        st.markdown(result["text"])
        st.download_button("⬇️ Download summary (.md)", result["text"], file_name="summary.md",
                           mime="text/markdown", key="summary_download")


# ======================================================================= Quiz
def _retake_quiz() -> None:
    quiz = st.session_state.get("quiz")
    if quiz:
        st.session_state["quiz_counter"] += 1
        quiz.update(id=st.session_state["quiz_counter"], submitted=False, picks=None, score=None)


def _render_quiz_results(quiz: dict) -> None:
    questions, picks, score = quiz["questions"], quiz["picks"], quiz["score"]
    total = len(questions)
    st.markdown(f"### Your score: {score} / {total}")
    st.progress(score / total)
    st.write(score_message(score, total))

    for i, (q, pick) in enumerate(zip(questions, picks), start=1):
        if pick is None:
            css, mark, yours = "skip", "⬜", "Not answered"
        elif pick == q.correct_index:
            css, mark, yours = "good", "✅", q.options[pick]
        else:
            css, mark, yours = "bad", "❌", q.options[pick]
        page = f" · page {q.page}" if q.page else ""
        st.markdown(
            f'<div class="result {css}"><b>{mark} Q{i}. {esc(q.question)}</b><br>'
            f"Your answer: {esc(yours)}<br>Correct answer: <b>{esc(q.correct_letter)}. {esc(q.correct_text)}</b><br>"
            f'<span class="card-muted">{esc(q.explanation)}{esc(page)}</span></div>',
            unsafe_allow_html=True,
        )
    st.button("🔁 Retake this quiz", on_click=_retake_quiz, key="retake_btn")


def render_quiz() -> None:
    page_header("🧠", "Quiz", "Multiple-choice questions made from your notes. Answer them, then see your score.")
    doc = require_document("quizzes")
    if doc is None:
        return
    ai_on = ai_ready()

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        count = c1.slider("Number of questions", 3, 15, 5, key="quiz_count")
        generate = c2.button("🎲 Generate quiz", type="primary", disabled=not ai_on, key="quiz_btn")

    if generate and ai_on:
        study_ai, error = _get_ai()
        if study_ai is None:
            st.error(error)
        else:
            try:
                with st.spinner("Writing your questions…"):
                    questions = study_ai.generate_quiz(doc.chunks, count)
            except AIServiceError as exc:
                st.error(str(exc))
            else:
                st.session_state["quiz_counter"] += 1
                st.session_state["quiz"] = {"id": st.session_state["quiz_counter"], "questions": questions,
                                            "submitted": False, "picks": None, "score": None}
                if len(questions) < count:
                    st.info(f"Only {len(questions)} valid question(s) could be made from this document.")

    quiz = st.session_state.get("quiz")
    if not quiz:
        st.caption("Click **Generate quiz** to begin.")
        return
    if quiz["submitted"]:
        _render_quiz_results(quiz)
        return

    questions = quiz["questions"]
    with st.form(f"quiz_form_{quiz['id']}"):
        for i, q in enumerate(questions):
            st.markdown(f"**Q{i + 1}. {q.question}**")
            st.radio("Choose an answer", q.options, index=None, key=f"quiz{quiz['id']}_{i}",
                     label_visibility="collapsed")
        submitted = st.form_submit_button("✅ Submit answers", type="primary")

    if submitted:
        picks = []
        for i, q in enumerate(questions):
            chosen = st.session_state.get(f"quiz{quiz['id']}_{i}")
            picks.append(q.options.index(chosen) if chosen in q.options else None)
        score = score_answers(questions, picks)
        quiz.update(submitted=True, picks=picks, score=score)
        _save_history("quiz", f"Quiz on {doc.name}", f"{score}/{len(questions)} correct",
                      document_id=doc.doc_id, score=score, total=len(questions))
        st.rerun()


# ======================================================================= Flashcards
def _card_next() -> None:
    deck = st.session_state["cards"]
    deck["index"] = min(deck["index"] + 1, len(deck["cards"]) - 1)
    deck["revealed"] = False


def _card_prev() -> None:
    deck = st.session_state["cards"]
    deck["index"] = max(deck["index"] - 1, 0)
    deck["revealed"] = False


def _card_flip() -> None:
    deck = st.session_state["cards"]
    deck["revealed"] = not deck["revealed"]


def _card_shuffle() -> None:
    deck = st.session_state["cards"]
    random.shuffle(deck["cards"])
    deck["index"], deck["revealed"] = 0, False


def render_flashcards() -> None:
    page_header("🗂️", "Flashcards", "Flip through question-and-answer cards made from your notes.")
    doc = require_document("flashcards")
    if doc is None:
        return
    ai_on = ai_ready()

    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        count = c1.slider("Number of cards", 5, 30, 10, key="card_count")
        generate = c2.button("🗂️ Generate cards", type="primary", disabled=not ai_on, key="cards_btn")

    if generate and ai_on:
        study_ai, error = _get_ai()
        if study_ai is None:
            st.error(error)
        else:
            try:
                with st.spinner("Making your flashcards…"):
                    cards = study_ai.generate_flashcards(doc.chunks, count)
            except AIServiceError as exc:
                st.error(str(exc))
            else:
                st.session_state["cards"] = {"cards": cards, "index": 0, "revealed": False}
                _save_history("flashcards", f"{len(cards)} flashcards from {doc.name}", "", document_id=doc.doc_id)

    deck = st.session_state.get("cards")
    if not deck:
        st.caption("Click **Generate cards** to begin.")
        return

    cards, index, revealed = deck["cards"], deck["index"], deck["revealed"]
    card = cards[index]
    label, text, css = ("Answer", card.back, "back") if revealed else ("Question", card.front, "front")
    page = f"From page {card.page}" if card.page else ""
    st.progress((index + 1) / len(cards), text=f"Card {index + 1} of {len(cards)}")
    st.markdown(
        f'<div class="flashcard {css}"><div class="fc-label">{label}</div>'
        f'<div class="fc-text">{esc(text)}</div><div class="fc-page">{esc(page)}</div></div>',
        unsafe_allow_html=True,
    )
    b1, b2, b3, b4 = st.columns(4)
    b1.button("⬅️ Previous", on_click=_card_prev, disabled=index == 0, key="card_prev")
    b2.button("🙈 Hide answer" if revealed else "👀 Show answer", on_click=_card_flip, type="primary", key="card_flip")
    b3.button("Next ➡️", on_click=_card_next, disabled=index >= len(cards) - 1, key="card_next")
    b4.button("🔀 Shuffle", on_click=_card_shuffle, key="card_shuffle")


# ======================================================================= History
def _clear_history() -> None:
    db.clear_history()
    st.toast("Study history cleared.", icon="🧹")


def render_history() -> None:
    page_header("📊", "Study History", "Your activity and uploaded-document records, stored on this computer.")

    stats = db.get_stats()
    cols = st.columns(5)
    cols[0].metric("Documents", stats["documents"])
    cols[1].metric("Questions", stats["questions"])
    cols[2].metric("Summaries", stats["summaries"])
    cols[3].metric("Quizzes", stats["quizzes"])
    avg = stats["avg_quiz_percent"]
    cols[4].metric("Avg quiz score", "–" if avg is None else f"{avg:g}%")

    st.subheader("Activity")
    labels = {"All activity": None, **{label: key for key, label in ACTIVITY_LABELS.items()}}
    chosen = st.selectbox("Show", list(labels), key="history_filter")
    items = db.list_history(limit=200, activity_type=labels[chosen])
    if items:
        st.dataframe(history_rows(items), hide_index=True)
    else:
        st.caption("Nothing here yet. Ask a question, make a summary or take a quiz.")

    st.subheader("Uploaded documents")
    st.caption("Only details about each file are saved, not the PDF or its text. Upload a file again to study it.")
    documents = db.list_documents()
    if documents:
        st.dataframe(document_rows(documents), hide_index=True)
        options = {f"#{d['id']} · {d['filename']}": d["id"] for d in documents}
        d1, d2 = st.columns([3, 1])
        picked = d1.selectbox("Remove a document record", list(options), key="delete_doc_pick")
        if d2.button("🗑️ Remove record", key="delete_doc_btn"):
            db.delete_document(options[picked])
            st.toast("Document record removed.", icon="🗑️")
            st.rerun()
    else:
        st.caption("No documents recorded yet.")

    with st.expander("⚠️ Danger zone"):
        sure = st.checkbox("I understand this permanently deletes my study history.", key="confirm_clear")
        st.button("Clear all study history", disabled=not sure, on_click=_clear_history, key="clear_history_btn")


PAGES = {
    "Documents": render_documents,
    "Ask Questions": render_chat,
    "Summaries": render_summaries,
    "Quiz": render_quiz,
    "Flashcards": render_flashcards,
    "History": render_history,
}

NAV_ICONS = {"Documents": "📄", "Ask Questions": "💬", "Summaries": "📝", "Quiz": "🧠",
             "Flashcards": "🗂️", "History": "📊"}
