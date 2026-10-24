"""Small text/table helpers for the UI. No Streamlit here, so they are easy to test."""

from __future__ import annotations

ACTIVITY_LABELS = {
    "question": "💬 Question",
    "summary": "📝 Summary",
    "quiz": "🧠 Quiz",
    "flashcards": "🗂️ Flashcards",
}

STATUS_LABELS = {
    "ready": "Ready",
    "ready_with_warnings": "Ready (with warnings)",
}


def truncate(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_timestamp(iso_text: str) -> str:
    """'2026-10-24T13:05:09+00:00' -> '2026-10-24 13:05 UTC'."""
    if not iso_text:
        return ""
    return iso_text.replace("T", " ")[:16] + " UTC"


def format_number(value: int) -> str:
    return f"{int(value):,}"


def history_rows(items: list[dict]) -> list[dict]:
    """Shape history rows for st.dataframe."""
    rows = []
    for item in items:
        result = item["detail"]
        if item["score"] is not None and item["total"]:
            result = f"{item['score']}/{item['total']}  ({round(100 * item['score'] / item['total'])}%)"
        rows.append({
            "When": format_timestamp(item["created_at"]),
            "Type": ACTIVITY_LABELS.get(item["activity_type"], item["activity_type"]),
            "Document": item["document_name"],
            "Title": truncate(item["title"], 90),
            "Result / details": truncate(result, 120),
        })
    return rows


def document_rows(items: list[dict]) -> list[dict]:
    """Shape document-metadata rows for st.dataframe."""
    return [{
        "ID": d["id"],
        "File": d["filename"],
        "Pages": d["page_count"],
        "Chunks": d["chunk_count"],
        "Characters": format_number(d["char_count"]),
        "Status": STATUS_LABELS.get(d["status"], d["status"]),
        "Uploaded": format_timestamp(d["uploaded_at"]),
    } for d in items]


def score_message(score: int, total: int) -> str:
    """A short encouraging message for a quiz result."""
    if total <= 0:
        return ""
    percent = 100 * score / total
    if percent == 100:
        return "Perfect score! 🎉"
    if percent >= 80:
        return "Great work! 👏"
    if percent >= 50:
        return "Good effort. Review the explanations below and try again."
    return "Keep going. Re-read the notes, then retake the quiz."
