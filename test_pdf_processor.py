"""Tests for src/pdf_processor.py

Tests that need the PyMuPDF library are skipped automatically when it is not
installed, so the rest of the suite still runs.
"""

import unittest
from pathlib import Path

from src.pdf_processor import (
    PDFError,
    ScannedPDFError,
    analyze_pages,
    clean_text,
    compute_hash,
    extract_pdf,
    validate_pdf_bytes,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def has_pymupdf() -> bool:
    try:
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            import fitz  # noqa: F401
        return True
    except ImportError:
        return False


class ValidateTests(unittest.TestCase):
    def test_empty_file_is_rejected(self):
        with self.assertRaisesRegex(PDFError, "empty"):
            validate_pdf_bytes(b"", "notes.pdf")

    def test_wrong_extension_is_rejected(self):
        with self.assertRaisesRegex(PDFError, ".pdf"):
            validate_pdf_bytes(b"%PDF-1.4 hello", "notes.txt")

    def test_missing_pdf_header_is_rejected(self):
        with self.assertRaisesRegex(PDFError, "real PDF"):
            validate_pdf_bytes(b"This is just text, renamed.", "notes.pdf")

    def test_too_large_file_is_rejected(self):
        with self.assertRaisesRegex(PDFError, "limit"):
            validate_pdf_bytes(b"%PDF-" + b"x" * 5000, "big.pdf", max_mb=0.001)

    def test_valid_looking_file_passes(self):
        validate_pdf_bytes(b"%PDF-1.7 rest of file", "ok.pdf")  # should not raise


class CleanTextTests(unittest.TestCase):
    def test_collapses_spaces_and_blank_lines(self):
        self.assertEqual(clean_text("a   b\n\n\n\nc"), "a b\n\nc")

    def test_joins_words_split_across_lines(self):
        self.assertEqual(clean_text("machine learn-\ning rocks"), "machine learning rocks")

    def test_removes_null_characters_and_trims(self):
        self.assertEqual(clean_text("  hi\x00 there  "), "hi there")

    def test_none_like_input_gives_empty_string(self):
        self.assertEqual(clean_text(""), "")


class AnalyzePagesTests(unittest.TestCase):
    GOOD = "This page has plenty of readable text about machine learning."

    def test_normal_document(self):
        result = analyze_pages([self.GOOD, self.GOOD], "a.pdf", "abc")
        self.assertEqual(result.page_count, 2)
        self.assertEqual([p.page_number for p in result.pages], [1, 2])
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.warnings, [])

    def test_scanned_document_raises_clear_error(self):
        with self.assertRaises(ScannedPDFError) as ctx:
            analyze_pages(["", "  ", "\n"], "scan.pdf")
        self.assertIn("scanned", str(ctx.exception).lower())

    def test_partly_empty_document_gets_a_warning(self):
        result = analyze_pages([self.GOOD, "", self.GOOD], "mixed.pdf")
        self.assertEqual(result.page_count, 3)
        self.assertEqual([p.page_number for p in result.pages], [1, 3])
        self.assertEqual(result.empty_pages, [2])
        self.assertEqual(result.status, "ready_with_warnings")
        self.assertIn("page 2", result.warnings[0])

    def test_zero_pages_raises(self):
        with self.assertRaises(PDFError):
            analyze_pages([], "none.pdf")

    def test_scanned_error_is_also_a_pdf_error(self):
        self.assertTrue(issubclass(ScannedPDFError, PDFError))


class HashTests(unittest.TestCase):
    def test_same_bytes_same_hash_different_bytes_different_hash(self):
        self.assertEqual(compute_hash(b"abc"), compute_hash(b"abc"))
        self.assertNotEqual(compute_hash(b"abc"), compute_hash(b"abd"))


@unittest.skipUnless(has_pymupdf(), "PyMuPDF is not installed (pip install pymupdf)")
class RealPDFTests(unittest.TestCase):
    def test_sample_notes_are_extracted(self):
        data = (SAMPLE_DIR / "sample_notes.pdf").read_bytes()
        result = extract_pdf(data, "sample_notes.pdf")
        self.assertEqual(result.page_count, 3)
        self.assertEqual(len(result.pages), 3)
        self.assertIn("machine learning", result.pages[0].text.lower())
        self.assertIn("overfitting", result.pages[1].text.lower())
        self.assertIn("precision", result.pages[2].text.lower())
        self.assertEqual(result.status, "ready")

    def test_scan_like_pdf_gives_scanned_error(self):
        data = (SAMPLE_DIR / "scan_like_blank.pdf").read_bytes()
        with self.assertRaises(ScannedPDFError):
            extract_pdf(data, "scan_like_blank.pdf")

    def test_corrupted_pdf_gives_friendly_error(self):
        with self.assertRaises(PDFError):
            extract_pdf(b"%PDF-1.4 this is not a real pdf body", "broken.pdf")


if __name__ == "__main__":
    unittest.main()
