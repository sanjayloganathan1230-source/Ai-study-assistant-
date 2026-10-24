"""Tests for src/document_loader.py and src/ui/formatting.py (no Streamlit needed)."""

import tempfile
import unittest
from pathlib import Path

from src import database as db
from src.document_loader import SAMPLE_DIR, load_pdf_bytes, load_sample_notes
from src.pdf_processor import PDFError, pymupdf_available
from src.ui.formatting import (
    document_rows,
    format_timestamp,
    history_rows,
    score_message,
    truncate,
)


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_sample_notes_load_and_are_searchable(self):
        doc = load_sample_notes(db_path=self.db_path)
        self.assertEqual(doc.page_count, 3)
        self.assertGreater(len(doc.chunks), 3)
        self.assertEqual(doc.status, "ready")
        hit = doc.store.search("What is overfitting?")[0]
        self.assertEqual(hit.page_number, 2)

    def test_metadata_is_saved_but_not_the_text(self):
        doc = load_sample_notes(db_path=self.db_path)
        row = db.get_document(doc.doc_id, self.db_path)
        self.assertEqual(row["page_count"], 3)
        self.assertEqual(row["chunk_count"], len(doc.chunks))
        self.assertGreater(row["char_count"], 1000)
        with db.get_connection(self.db_path) as conn:
            everything = " ".join(str(v) for r in conn.execute("SELECT * FROM documents") for v in tuple(r))
        self.assertNotIn("Overfitting happens when", everything)

    def test_loading_the_same_file_twice_reuses_the_record(self):
        first = load_sample_notes(db_path=self.db_path)
        second = load_sample_notes(db_path=self.db_path)
        self.assertFalse(first.previously_uploaded)
        self.assertTrue(second.previously_uploaded)
        self.assertEqual(first.doc_id, second.doc_id)
        self.assertEqual(len(db.list_documents(self.db_path)), 1)

    def test_missing_sample_files_give_friendly_error(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(PDFError):
                load_sample_notes(db_path=self.db_path, sample_dir=Path(empty))

    def test_non_pdf_upload_is_rejected_before_anything_is_saved(self):
        with self.assertRaises(PDFError):
            load_pdf_bytes(b"just some text", "notes.pdf", db_path=self.db_path)
        with self.assertRaises(PDFError):
            load_pdf_bytes(b"%PDF-1.4 ok", "notes.docx", db_path=self.db_path)
        self.assertEqual(db.list_documents(self.db_path), [])

    @unittest.skipUnless(pymupdf_available(), "PyMuPDF is not installed")
    def test_real_pdf_upload_pipeline(self):
        data = (SAMPLE_DIR / "sample_notes.pdf").read_bytes()
        doc = load_pdf_bytes(data, "my_notes.pdf", db_path=self.db_path)
        self.assertEqual(doc.name, "my_notes.pdf")
        self.assertEqual(doc.store.search("precision and recall")[0].page_number, 3)

    @unittest.skipUnless(pymupdf_available(), "PyMuPDF is not installed")
    def test_scanned_pdf_is_rejected_and_not_saved(self):
        data = (SAMPLE_DIR / "scan_like_blank.pdf").read_bytes()
        with self.assertRaises(PDFError):
            load_pdf_bytes(data, "scan.pdf", db_path=self.db_path)
        self.assertEqual(db.list_documents(self.db_path), [])


class FormattingTests(unittest.TestCase):
    def test_truncate(self):
        self.assertEqual(truncate("short", 10), "short")
        self.assertEqual(len(truncate("word " * 50, 20)), 20)
        self.assertTrue(truncate("word " * 50, 20).endswith("…"))
        self.assertEqual(truncate(None, 5), "")

    def test_format_timestamp(self):
        self.assertEqual(format_timestamp("2026-10-24T13:05:09+00:00"), "2026-10-24 13:05 UTC")
        self.assertEqual(format_timestamp(""), "")

    def test_history_rows_show_quiz_percentage(self):
        item = {"created_at": "2026-10-24T13:05:09+00:00", "activity_type": "quiz", "document_name": "n.pdf",
                "title": "Quiz", "detail": "", "score": 4, "total": 5}
        row = history_rows([item])[0]
        self.assertIn("4/5", row["Result / details"])
        self.assertIn("80%", row["Result / details"])
        self.assertIn("Quiz", row["Type"])

    def test_history_rows_for_non_quiz_use_detail_text(self):
        item = {"created_at": "2026-10-24T13:05:09+00:00", "activity_type": "question", "document_name": "n.pdf",
                "title": "What is ML?", "detail": "Learning from data", "score": None, "total": None}
        self.assertEqual(history_rows([item])[0]["Result / details"], "Learning from data")

    def test_document_rows(self):
        doc = {"id": 1, "filename": "a.pdf", "page_count": 3, "chunk_count": 9, "char_count": 12345,
               "status": "ready_with_warnings", "uploaded_at": "2026-10-24T13:05:09+00:00"}
        row = document_rows([doc])[0]
        self.assertEqual(row["Characters"], "12,345")
        self.assertEqual(row["Status"], "Ready (with warnings)")

    def test_score_messages(self):
        self.assertIn("Perfect", score_message(5, 5))
        self.assertIn("Great", score_message(4, 5))
        self.assertIn("Keep going", score_message(1, 5))
        self.assertEqual(score_message(0, 0), "")


if __name__ == "__main__":
    unittest.main()
