"""Read a PDF and turn it into clean text, page by page.

Steps:
    1. validate_pdf_bytes()  - is this really a usable PDF? (size, type, header)
    2. extract_pdf()         - PyMuPDF reads the text of every page
    3. analyze_pages()       - clean the text, detect empty/scanned pages

Important limitation:
    A *scanned* PDF is just pictures of pages, so there is no text to extract.
    This project does not do OCR. For scanned files we show a clear message
    instead of pretending that everything worked.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from src import config


class PDFError(Exception):
    """A problem with the uploaded file. The message is safe to show to the user."""


class ScannedPDFError(PDFError):
    """The PDF has pages but no readable text (probably scanned images)."""


@dataclass
class PageText:
    page_number: int  # 1-based, matches what you see in a PDF viewer
    text: str


@dataclass
class ProcessedPDF:
    filename: str
    file_hash: str
    page_count: int                      # total pages in the PDF
    pages: list[PageText]                # only pages that contain readable text
    empty_pages: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return sum(len(p.text) for p in self.pages)

    @property
    def status(self) -> str:
        return "ready_with_warnings" if self.warnings else "ready"


def pymupdf_available() -> bool:
    """True if the PyMuPDF library can be imported."""
    try:
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def compute_hash(data: bytes) -> str:
    """A fingerprint of the file. Same file -> same hash (lets us spot re-uploads)."""
    return hashlib.sha256(data).hexdigest()


def clean_text(raw: str) -> str:
    """Tidy up text extracted from a PDF."""
    if not raw:
        return ""
    text = raw.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words split across lines: "learn-\ning"
    text = re.sub(r"[ \t\f\v]+", " ", text)        # collapse repeated spaces
    text = re.sub(r" *\n *", "\n", text)           # trim spaces around line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)         # at most one blank line in a row
    return text.strip()


def validate_pdf_bytes(data: bytes, filename: str, max_mb: float | None = None) -> None:
    """Raise PDFError with a friendly message if the upload is not acceptable."""
    limit_mb = max_mb if max_mb is not None else config.MAX_UPLOAD_MB
    if not filename or not filename.lower().endswith(".pdf"):
        raise PDFError("Please upload a file with the .pdf extension.")
    if not data:
        raise PDFError("The file is empty (0 bytes).")
    if len(data) > limit_mb * 1024 * 1024:
        size_mb = len(data) / (1024 * 1024)
        raise PDFError(f"The file is {size_mb:.1f} MB, but the limit is {limit_mb:g} MB.")
    if b"%PDF-" not in data[:1024]:
        raise PDFError("This does not look like a real PDF file (missing the PDF header).")


def analyze_pages(page_texts: list[str], filename: str, file_hash: str = "") -> ProcessedPDF:
    """Clean raw page texts and decide whether the document is usable.

    This function does not need PyMuPDF, so it is easy to test on its own.
    """
    if not page_texts:
        raise PDFError("This PDF has no pages.")

    cleaned = [PageText(i + 1, clean_text(t)) for i, t in enumerate(page_texts)]
    good = [p for p in cleaned if len(p.text) >= config.MIN_TEXT_CHARS_PER_PAGE]
    empty = [p.page_number for p in cleaned if len(p.text) < config.MIN_TEXT_CHARS_PER_PAGE]

    if not good:
        raise ScannedPDFError(
            "No readable text was found. This PDF is probably scanned (pages are images). "
            "Please upload a text-based PDF, or run OCR on it first."
        )

    warnings: list[str] = []
    if empty:
        shown = ", ".join(str(n) for n in empty[:10]) + (" ..." if len(empty) > 10 else "")
        warnings.append(
            f"{len(empty)} page(s) had little or no readable text and were skipped (page {shown}). "
            "They may be images or scans."
        )

    return ProcessedPDF(
        filename=filename,
        file_hash=file_hash,
        page_count=len(cleaned),
        pages=good,
        empty_pages=empty,
        warnings=warnings,
    )


def extract_pdf(data: bytes, filename: str, max_mb: float | None = None) -> ProcessedPDF:
    """Validate a PDF (given as bytes) and extract its text with PyMuPDF."""
    validate_pdf_bytes(data, filename, max_mb)

    try:
        try:
            import pymupdf as fitz  # newer name
        except ImportError:
            import fitz  # older name of the same library
    except ImportError as exc:
        raise PDFError("PyMuPDF is not installed. Run: pip install -r requirements.txt") from exc

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # corrupted or not a real PDF
        raise PDFError("The PDF could not be opened. It may be corrupted.") from exc

    with doc:
        if doc.needs_pass:
            raise PDFError("This PDF is password-protected. Please remove the password and try again.")
        if doc.page_count > config.MAX_PAGES:
            raise PDFError(f"This PDF has {doc.page_count} pages; the limit is {config.MAX_PAGES}.")
        try:
            texts = [page.get_text("text") for page in doc]
        except Exception as exc:
            raise PDFError("The PDF opened, but its text could not be read.") from exc

    return analyze_pages(texts, filename, compute_hash(data))
