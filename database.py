"""SQLite database: document metadata and study history.

What is stored (and what is NOT):
    STORED     - file name, page count, chunk count, a SHA-256 fingerprint of the
                 file, upload time, and short study-history entries (the question
                 asked, quiz score, etc.).
    NOT STORED - the PDF file itself and its full text. Those live only in
                 memory while the app is running, which keeps the database small
                 and avoids keeping your notes on disk without need.

SQLite is a database that lives in a single file (data/study_assistant.db).
Python includes the `sqlite3` module, so nothing extra needs installing.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from src import config

ACTIVITY_TYPES = ("question", "summary", "quiz", "flashcards")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    file_hash   TEXT    NOT NULL,
    page_count  INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    char_count  INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL,
    uploaded_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);

CREATE TABLE IF NOT EXISTS history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id   INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    document_name TEXT    NOT NULL DEFAULT '',
    activity_type TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    detail        TEXT    NOT NULL DEFAULT '',
    score         INTEGER,
    total         INTEGER,
    created_at    TEXT    NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clip(text: str, limit: int) -> str:
    """Shorten text so we never store large pieces of content."""
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


@contextmanager
def get_connection(db_path: str | Path | None = None):
    """Open the database, make sure the tables exist, and commit/close safely."""
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)  # harmless if the tables already exist
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Create the database file and tables if they do not exist yet."""
    with get_connection(db_path):
        pass


# ------------------------------------------------------------------ documents
def add_document(
    filename: str,
    file_hash: str,
    page_count: int,
    chunk_count: int,
    char_count: int,
    status: str,
    db_path: str | Path | None = None,
) -> int:
    """Save metadata about an uploaded document. Returns its new id."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO documents (filename, file_hash, page_count, chunk_count,"
            " char_count, status, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_clip(filename, 255), file_hash, page_count, chunk_count, char_count, status, _now()),
        )
        return int(cur.lastrowid)


def find_document_by_hash(file_hash: str, db_path: str | Path | None = None) -> dict | None:
    """Return the document with this fingerprint, if it was uploaded before."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE file_hash = ? ORDER BY id DESC LIMIT 1", (file_hash,)
        ).fetchone()
        return dict(row) if row else None


def get_document(doc_id: int, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None


def list_documents(db_path: str | Path | None = None) -> list[dict]:
    """All uploaded documents, newest first."""
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def update_document_status(doc_id: int, status: str, db_path: str | Path | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE documents SET status = ? WHERE id = ?", (status, doc_id))


def delete_document(doc_id: int, db_path: str | Path | None = None) -> None:
    """Remove a document's metadata. Its history rows stay (with the name kept)."""
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# -------------------------------------------------------------------- history
def add_history(
    activity_type: str,
    title: str,
    detail: str = "",
    document_id: int | None = None,
    score: int | None = None,
    total: int | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Record one study activity (a question, a summary, a quiz result...)."""
    if activity_type not in ACTIVITY_TYPES:
        raise ValueError(f"activity_type must be one of {ACTIVITY_TYPES}, got {activity_type!r}")
    with get_connection(db_path) as conn:
        name = ""
        if document_id is not None:
            row = conn.execute("SELECT filename FROM documents WHERE id = ?", (document_id,)).fetchone()
            name = row["filename"] if row else ""
        cur = conn.execute(
            "INSERT INTO history (document_id, document_name, activity_type, title, detail,"
            " score, total, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (document_id, name, activity_type, _clip(title, 200), _clip(detail, 1000), score, total, _now()),
        )
        return int(cur.lastrowid)


def list_history(
    limit: int = 50, activity_type: str | None = None, db_path: str | Path | None = None
) -> list[dict]:
    """Most recent study activity first."""
    query = "SELECT * FROM history"
    params: list = []
    if activity_type:
        query += " WHERE activity_type = ?"
        params.append(activity_type)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_connection(db_path) as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def clear_history(db_path: str | Path | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM history")


def get_stats(db_path: str | Path | None = None) -> dict:
    """Small numbers for the dashboard home page."""
    with get_connection(db_path) as conn:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        counts = {
            row["activity_type"]: row["n"]
            for row in conn.execute("SELECT activity_type, COUNT(*) AS n FROM history GROUP BY activity_type")
        }
        avg = conn.execute(
            "SELECT AVG(100.0 * score / total) FROM history"
            " WHERE activity_type = 'quiz' AND total > 0 AND score IS NOT NULL"
        ).fetchone()[0]
    return {
        "documents": docs,
        "questions": counts.get("question", 0),
        "summaries": counts.get("summary", 0),
        "quizzes": counts.get("quiz", 0),
        "flashcard_sets": counts.get("flashcards", 0),
        "avg_quiz_percent": round(avg, 1) if avg is not None else None,
    }
