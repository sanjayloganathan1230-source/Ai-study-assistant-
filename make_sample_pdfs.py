"""Build the two sample PDFs used for testing (developer tool, not needed to run the app).

    python scripts/make_sample_pdfs.py

Creates:
    sample_data/sample_notes.pdf     - 3 text pages made from sample_notes.txt
    sample_data/scan_like_blank.pdf  - 1 page with only drawn shapes and NO text,
                                       used to test the "scanned PDF" message

This script needs `reportlab` (pip install reportlab). The finished PDFs are
saved in the repository, so you only need to re-run it if you edit the notes.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "sample_data"
MARGIN = 56
FONT, FONT_BOLD, SIZE, LEADING = "Helvetica", "Helvetica-Bold", 11, 15


def build_notes_pdf() -> int:
    raw = (SAMPLE_DIR / "sample_notes.txt").read_text(encoding="utf-8")
    pages = [block.strip() for block in raw.split("=== PAGE ===") if block.strip()]

    width, height = A4
    pdf = canvas.Canvas(str(SAMPLE_DIR / "sample_notes.pdf"), pagesize=A4)
    pdf.setTitle("Sample Notes - Introduction to Machine Learning")

    for block in pages:
        lines = block.split("\n")
        y = height - MARGIN
        pdf.setFont(FONT_BOLD, 16)
        pdf.drawString(MARGIN, y, lines[0])  # first line of each page is its heading
        y -= 30
        pdf.setFont(FONT, SIZE)
        for paragraph in lines[1:]:
            for line in simpleSplit(paragraph, FONT, SIZE, width - 2 * MARGIN):
                pdf.drawString(MARGIN, y, line)
                y -= LEADING
            y -= 8  # gap between paragraphs
        pdf.showPage()
    pdf.save()
    return len(pages)


def build_scan_like_pdf() -> None:
    """A page with shapes only. It has no text, just like a scanned page has no text."""
    width, height = A4
    pdf = canvas.Canvas(str(SAMPLE_DIR / "scan_like_blank.pdf"), pagesize=A4)
    pdf.setTitle("Scan-like page (no text)")
    pdf.setFillGray(0.85)
    pdf.rect(MARGIN, MARGIN, width - 2 * MARGIN, height - 2 * MARGIN, fill=1, stroke=1)
    pdf.setStrokeGray(0.4)
    for i in range(10):
        y = height - 120 - i * 28
        pdf.line(MARGIN + 20, y, width - MARGIN - 20, y)
    pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    count = build_notes_pdf()
    build_scan_like_pdf()
    print(f"Created sample_notes.pdf ({count} pages) and scan_like_blank.pdf in {SAMPLE_DIR}")
