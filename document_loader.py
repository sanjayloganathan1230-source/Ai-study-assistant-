"""Turn an uploaded PDF into a ready-to-study document.

This is the "pipeline" used by the dashboard:

    PDF bytes -> extract text (pdf_processor) -> split into chunks (chunker)
              -> build the search index (retrieval) -> save metadata (database)

It contains no Streamlit code, so it can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src import database as db
from src.chunker import Chunk, chunk_pages
from src.pdf_processor import (
    PDFError,
    ProcessedPDF,
    analyze_pages,
    compute_hash,
    extract_pdf,
    pymupdf_available,
)
from src.retrieval import VectorStore

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
PAGE_MARKER = "=== PAGE ==="


@dataclass
class LoadedDocument:
    """Everything the app needs about the document being studied (kept in memory)."""

    doc_id: int
    processed: ProcessedPDF
    chunks: list[Chunk]
    store: VectorStore
    previously_uploaded: bool = False

    @property
    def name(self) -> str:
        return self.processed.filename

    @property
    def page_count(self) -> int:
        return self.processed.page_count

    @property
    def status(self) -> str:
        return self.processed.status

    @property
    def warnings(self) -> list[str]:
        return self.processed.warnings


def build_document(processed: ProcessedPDF, db_path=None) -> LoadedDocument:
    """Chunk the text, build the search index, and record metadata in SQLite."""
    chunks = chunk_pages(processed.pages)
    if not chunks:
        raise PDFError("No text could be prepared from this PDF.")

    store = VectorStore()
    store.build(chunks)

    existing = db.find_document_by_hash(processed.file_hash, db_path) if processed.file_hash else None
    if existing:
        doc_id, previously = existing["id"], True
    else:
        doc_id = db.add_document(
            filename=processed.filename,
            file_hash=processed.file_hash,
            page_count=processed.page_count,
            chunk_count=len(chunks),
            char_count=processed.total_chars,
            status=processed.status,
            db_path=db_path,
        )
        previously = False
    return LoadedDocument(doc_id, processed, chunks, store, previously)


def load_pdf_bytes(data: bytes, filename: str, db_path=None) -> LoadedDocument:
    """Full pipeline for an uploaded PDF. Raises PDFError with a friendly message."""
    return build_document(extract_pdf(data, filename), db_path)


def load_sample_notes(db_path=None, sample_dir: Path | None = None) -> LoadedDocument:
    """Load the bundled sample notes so the app can be tried without any upload.

    Uses the sample PDF when PyMuPDF is installed; otherwise falls back to the
    plain-text version of the same notes.
    """
    folder = Path(sample_dir) if sample_dir else SAMPLE_DIR
    pdf_path = folder / "sample_notes.pdf"
    if pymupdf_available() and pdf_path.exists():
        return load_pdf_bytes(pdf_path.read_bytes(), "sample_notes.pdf", db_path)

    txt_path = folder / "sample_notes.txt"
    if not txt_path.exists():
        raise PDFError("The sample notes are missing from the sample_data folder.")
    raw = txt_path.read_bytes()
    blocks = [b.strip() for b in raw.decode("utf-8").split(PAGE_MARKER) if b.strip()]
    processed = analyze_pages(blocks, "sample_notes.txt", compute_hash(raw))
    return build_document(processed, db_path)
