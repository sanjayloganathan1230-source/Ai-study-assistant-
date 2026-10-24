"""Opens the real dashboard with Streamlit's own test runner (AppTest).

These tests are skipped automatically when Streamlit is not installed.
They use a temporary database and no API key, so nothing real is touched or called.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # Streamlit not installed
    AppTest = None

APP_FILE = str(Path(__file__).resolve().parent.parent / "app.py")


@unittest.skipIf(AppTest is None, "Streamlit is not installed (pip install streamlit)")
class DashboardSmokeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patches = [
            mock.patch("src.config.DB_PATH", Path(self._tmp.name) / "ui_test.db"),
            mock.patch("src.config.get_api_key", return_value=None),  # AI switched off
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmp.cleanup)

    def new_app(self) -> "AppTest":
        return AppTest.from_file(APP_FILE, default_timeout=60).run()

    def test_first_page_opens_without_errors(self):
        at = self.new_app()
        self.assertEqual(len(at.exception), 0)

    def test_every_page_opens_without_a_document(self):
        at = self.new_app()
        for page in ["Ask Questions", "Summaries", "Quiz", "Flashcards", "History", "Documents"]:
            at.sidebar.radio(key="nav").set_value(page).run()
            self.assertEqual(len(at.exception), 0, msg=f"error on page {page}")

    def test_sample_notes_load_and_pages_work(self):
        at = self.new_app()
        at.button(key="sample_btn").click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIsNotNone(at.session_state["doc"])
        self.assertEqual(at.session_state["doc"].page_count, 3)
        for page in ["Ask Questions", "Summaries", "Quiz", "Flashcards", "History"]:
            at.sidebar.radio(key="nav").set_value(page).run()
            self.assertEqual(len(at.exception), 0, msg=f"error on page {page}")

    def test_ai_buttons_are_disabled_without_an_api_key(self):
        at = self.new_app()
        at.button(key="sample_btn").click().run()
        at.sidebar.radio(key="nav").set_value("Quiz").run()
        self.assertTrue(at.button(key="quiz_btn").disabled)

    def test_chat_without_api_key_shows_passages_not_a_fake_answer(self):
        at = self.new_app()
        at.button(key="sample_btn").click().run()
        at.sidebar.radio(key="nav").set_value("Ask Questions").run()
        at.chat_input[0].set_value("What is overfitting?").run()
        self.assertEqual(len(at.exception), 0)
        reply = at.session_state["chat"][-1]
        self.assertEqual(reply["mode"], "search")
        self.assertEqual(reply["sources"][0]["page"], 2)


if __name__ == "__main__":
    unittest.main()
