"""Tests for src/database.py (uses a throw-away database file for every test)."""

import tempfile
import unittest
from pathlib import Path

from src import database as db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"

    def tearDown(self):
        self._tmp.cleanup()

    def add_doc(self, name="notes.pdf", file_hash="h1"):
        return db.add_document(name, file_hash, page_count=3, chunk_count=9, char_count=4000,
                               status="ready", db_path=self.db_path)

    def test_add_and_get_document(self):
        doc_id = self.add_doc()
        doc = db.get_document(doc_id, self.db_path)
        self.assertEqual(doc["filename"], "notes.pdf")
        self.assertEqual(doc["page_count"], 3)
        self.assertEqual(doc["chunk_count"], 9)
        self.assertEqual(doc["status"], "ready")

    def test_database_stores_no_pdf_text_column(self):
        with db.get_connection(self.db_path) as conn:
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(documents)")}
        self.assertFalse({"text", "content", "pdf", "data"} & columns)

    def test_find_document_by_hash(self):
        self.add_doc(file_hash="same")
        self.assertIsNotNone(db.find_document_by_hash("same", self.db_path))
        self.assertIsNone(db.find_document_by_hash("other", self.db_path))

    def test_list_documents_newest_first(self):
        first = self.add_doc("a.pdf", "1")
        second = self.add_doc("b.pdf", "2")
        ids = [d["id"] for d in db.list_documents(self.db_path)]
        self.assertEqual(ids, [second, first])

    def test_update_status(self):
        doc_id = self.add_doc()
        db.update_document_status(doc_id, "failed", self.db_path)
        self.assertEqual(db.get_document(doc_id, self.db_path)["status"], "failed")

    def test_history_records_document_name(self):
        doc_id = self.add_doc("chapter1.pdf")
        db.add_history("question", "What is ML?", "Answer text", document_id=doc_id, db_path=self.db_path)
        row = db.list_history(db_path=self.db_path)[0]
        self.assertEqual(row["document_name"], "chapter1.pdf")
        self.assertEqual(row["activity_type"], "question")

    def test_history_survives_document_deletion(self):
        doc_id = self.add_doc("gone.pdf")
        db.add_history("summary", "Short summary", document_id=doc_id, db_path=self.db_path)
        db.delete_document(doc_id, self.db_path)
        row = db.list_history(db_path=self.db_path)[0]
        self.assertIsNone(row["document_id"])
        self.assertEqual(row["document_name"], "gone.pdf")

    def test_long_history_text_is_clipped(self):
        db.add_history("question", "q" * 1000, "d" * 5000, db_path=self.db_path)
        row = db.list_history(db_path=self.db_path)[0]
        self.assertLessEqual(len(row["title"]), 200)
        self.assertLessEqual(len(row["detail"]), 1000)

    def test_invalid_activity_type_is_rejected(self):
        with self.assertRaises(ValueError):
            db.add_history("hacking", "x", db_path=self.db_path)

    def test_filter_history_by_type(self):
        db.add_history("question", "q1", db_path=self.db_path)
        db.add_history("quiz", "quiz1", score=3, total=5, db_path=self.db_path)
        rows = db.list_history(activity_type="quiz", db_path=self.db_path)
        self.assertEqual([r["title"] for r in rows], ["quiz1"])

    def test_stats(self):
        self.add_doc()
        db.add_history("question", "q1", db_path=self.db_path)
        db.add_history("question", "q2", db_path=self.db_path)
        db.add_history("quiz", "quiz A", score=4, total=5, db_path=self.db_path)
        db.add_history("quiz", "quiz B", score=2, total=5, db_path=self.db_path)
        stats = db.get_stats(self.db_path)
        self.assertEqual(stats["documents"], 1)
        self.assertEqual(stats["questions"], 2)
        self.assertEqual(stats["quizzes"], 2)
        self.assertEqual(stats["avg_quiz_percent"], 60.0)

    def test_stats_on_empty_database(self):
        stats = db.get_stats(self.db_path)
        self.assertEqual(stats["documents"], 0)
        self.assertIsNone(stats["avg_quiz_percent"])

    def test_clear_history(self):
        db.add_history("question", "q", db_path=self.db_path)
        db.clear_history(self.db_path)
        self.assertEqual(db.list_history(db_path=self.db_path), [])


if __name__ == "__main__":
    unittest.main()
