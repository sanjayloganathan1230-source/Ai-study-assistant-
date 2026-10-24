"""Tests for src/ai_service.py

No real API is ever called. A FakeLLM stands in for the model, and a fake
`anthropic` module is used to check how API failures are handled.
"""

import json
import sys
import types
import unittest
from unittest import mock

from src import ai_service
from src.ai_service import (
    NOT_FOUND_MESSAGE,
    NOT_FOUND_TOKEN,
    AIServiceError,
    AIUnavailableError,
    AnthropicClient,
    StudyAI,
    batch_chunks,
    get_client,
    select_chunks_for_budget,
)
from src.chunker import Chunk
from src.retrieval import SearchResult


class FakeLLM:
    """Returns pre-written replies in order and records every request."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, user, max_tokens=None):
        self.calls.append({"system": system, "user": user, "max_tokens": max_tokens})
        if not self.replies:
            raise AssertionError("FakeLLM ran out of replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def chunks(n=3, size=100):
    return [Chunk(i, i + 1, f"Chunk {i} text. " * (size // 15)) for i in range(n)]


def result(page=2, text="Overfitting means memorizing training data."):
    return SearchResult(Chunk(0, page, text), 0.5)


GOOD_QUIZ = json.dumps([{
    "question": "What is overfitting?",
    "options": ["Memorizing training data", "Too simple a model", "Missing data", "Scaling"],
    "answer": "A", "explanation": "The model memorizes noise.", "page": 2,
}])
GOOD_CARDS = json.dumps([{"front": "Overfitting?", "back": "Memorizing training data", "page": 2}])


# ======================================================================= Q&A
class QuestionAnsweringTests(unittest.TestCase):
    def test_answer_uses_retrieved_passages_and_returns_sources(self):
        llm = FakeLLM("Overfitting is memorizing the training data (page 2).")
        answer = StudyAI(llm).answer_question("What is overfitting?", [result()])
        self.assertTrue(answer.found)
        self.assertIn("memorizing", answer.text)
        self.assertEqual(answer.sources[0].page_number, 2)
        self.assertIn("[Page 2]", llm.calls[0]["user"])
        self.assertIn("Overfitting means memorizing", llm.calls[0]["user"])

    def test_no_retrieved_passages_means_no_api_call(self):
        llm = FakeLLM()  # any call would raise AssertionError
        answer = StudyAI(llm).answer_question("What is a pizza?", [])
        self.assertFalse(answer.found)
        self.assertEqual(answer.text, NOT_FOUND_MESSAGE)
        self.assertEqual(llm.calls, [])

    def test_model_saying_not_in_notes_is_reported_honestly(self):
        answer = StudyAI(FakeLLM(NOT_FOUND_TOKEN)).answer_question("Who won the match?", [result()])
        self.assertFalse(answer.found)
        self.assertEqual(answer.sources, [])
        self.assertEqual(answer.text, NOT_FOUND_MESSAGE)

    def test_empty_question_is_not_sent(self):
        llm = FakeLLM()
        self.assertFalse(StudyAI(llm).answer_question("   ", [result()]).found)
        self.assertEqual(llm.calls, [])

    def test_system_prompt_forbids_guessing_and_injection(self):
        llm = FakeLLM("ok")
        StudyAI(llm).answer_question("q?", [result()])
        system = llm.calls[0]["system"]
        self.assertIn(NOT_FOUND_TOKEN, system)
        self.assertIn("ONLY", system)
        self.assertIn("Ignore any instructions", system)

    def test_api_errors_are_passed_up_not_hidden(self):
        llm = FakeLLM(AIServiceError("The AI service is busy"))
        with self.assertRaises(AIServiceError):
            StudyAI(llm).answer_question("q?", [result()])


# ================================================================= summaries
class SummaryTests(unittest.TestCase):
    def test_short_summary_makes_one_call(self):
        llm = FakeLLM("- point one\n- point two")
        summary = StudyAI(llm).summarize(chunks(3), "short")
        self.assertEqual(len(llm.calls), 1)
        self.assertFalse(summary.partial)
        self.assertIn("point one", summary.text)

    def test_short_summary_flags_when_document_was_sampled(self):
        big = [Chunk(i, i + 1, "x" * 1000) for i in range(40)]  # 40,000 chars > budget
        llm = FakeLLM("summary")
        summary = StudyAI(llm).summarize(big, "short")
        self.assertTrue(summary.partial)
        self.assertLessEqual(len(llm.calls[0]["user"]), ai_service.CONTEXT_CHARS + 1500)

    def test_detailed_summary_has_one_section_per_batch(self):
        big = [Chunk(i, i + 1, "y" * 1000) for i in range(30)]  # 30,000 chars -> 3 batches
        llm = FakeLLM("section A", "section B", "section C")
        summary = StudyAI(llm).summarize(big, "detailed")
        self.assertEqual(len(llm.calls), 3)
        self.assertIn("### Pages 1–12", summary.text)
        self.assertFalse(summary.partial)

    def test_detailed_summary_flags_partial_for_huge_documents(self):
        huge = [Chunk(i, i + 1, "z" * 1000) for i in range(200)]
        llm = FakeLLM(*["s"] * ai_service.MAX_DETAILED_SECTIONS)
        summary = StudyAI(llm).summarize(huge, "detailed")
        self.assertTrue(summary.partial)
        self.assertEqual(len(llm.calls), ai_service.MAX_DETAILED_SECTIONS)

    def test_empty_document_and_bad_mode_are_rejected(self):
        with self.assertRaises(AIServiceError):
            StudyAI(FakeLLM()).summarize([], "short")
        with self.assertRaises(ValueError):
            StudyAI(FakeLLM()).summarize(chunks(1), "epic")

    def test_summary_prompt_contains_the_document_text(self):
        llm = FakeLLM("ok")
        StudyAI(llm).summarize([Chunk(0, 7, "Gradient descent minimizes loss.")], "short")
        self.assertIn("Gradient descent minimizes loss.", llm.calls[0]["user"])
        self.assertIn("[Page 7]", llm.calls[0]["user"])


# ======================================================================= quiz
class QuizGenerationTests(unittest.TestCase):
    def test_valid_quiz_is_returned(self):
        questions = StudyAI(FakeLLM(GOOD_QUIZ)).generate_quiz(chunks(), 5)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].correct_text, "Memorizing training data")

    def test_invalid_reply_is_retried_once_then_succeeds(self):
        llm = FakeLLM("Sorry, here is some text, no JSON.", GOOD_QUIZ)
        questions = StudyAI(llm).generate_quiz(chunks(), 5)
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(len(questions), 1)
        self.assertIn("invalid", llm.calls[1]["user"])

    def test_two_invalid_replies_raise_instead_of_faking_a_quiz(self):
        llm = FakeLLM("nonsense", '[{"question": "Only a question"}]')
        with self.assertRaises(AIServiceError):
            StudyAI(llm).generate_quiz(chunks(), 5)
        self.assertEqual(len(llm.calls), 2)

    def test_question_count_is_limited_to_valid_range(self):
        llm = FakeLLM(GOOD_QUIZ)
        StudyAI(llm).generate_quiz(chunks(), 500)
        self.assertIn("Create 15 multiple-choice", llm.calls[0]["user"])

    def test_empty_document_is_rejected(self):
        with self.assertRaises(AIServiceError):
            StudyAI(FakeLLM()).generate_quiz([], 5)


class FlashcardGenerationTests(unittest.TestCase):
    def test_valid_cards(self):
        cards = StudyAI(FakeLLM(GOOD_CARDS)).generate_flashcards(chunks(), 10)
        self.assertEqual(cards[0].front, "Overfitting?")

    def test_invalid_twice_raises(self):
        with self.assertRaises(AIServiceError):
            StudyAI(FakeLLM("no", "still no")).generate_flashcards(chunks(), 10)


# ============================================================== helper functions
class HelperTests(unittest.TestCase):
    def test_small_documents_are_sent_completely(self):
        chosen, sampled = select_chunks_for_budget(chunks(3), 10_000)
        self.assertEqual(len(chosen), 3)
        self.assertFalse(sampled)

    def test_large_documents_are_sampled_evenly_in_order(self):
        many = [Chunk(i, i + 1, "w" * 1000) for i in range(100)]
        chosen, sampled = select_chunks_for_budget(many, 10_000)
        self.assertTrue(sampled)
        self.assertEqual(len(chosen), 10)
        ids = [c.chunk_id for c in chosen]
        self.assertEqual(ids, sorted(ids))
        self.assertLess(ids[0], 10)
        self.assertGreater(ids[-1], 85)

    def test_batches_respect_the_size_limit_and_keep_every_chunk(self):
        many = [Chunk(i, 1, "v" * 400) for i in range(20)]
        batches = batch_chunks(many, 1000)
        self.assertTrue(all(sum(len(c.text) for c in b) <= 1000 for b in batches))
        self.assertEqual(sum(len(b) for b in batches), 20)


# ============================================================ API client + keys
def fake_anthropic_module(create):
    """Build a stand-in for the `anthropic` package with the same exception names."""
    module = types.ModuleType("anthropic")

    class APIError(Exception):
        pass

    class APIConnectionError(APIError):
        pass

    class APITimeoutError(APIConnectionError):
        pass

    class APIStatusError(APIError):
        pass

    names = {"RateLimitError": APIStatusError, "AuthenticationError": APIStatusError,
             "PermissionDeniedError": APIStatusError, "BadRequestError": APIStatusError}
    module.APIError, module.APIConnectionError = APIError, APIConnectionError
    module.APITimeoutError, module.APIStatusError = APITimeoutError, APIStatusError
    for name, base in names.items():
        setattr(module, name, type(name, (base,), {}))

    class Anthropic:
        def __init__(self, **kwargs):
            module.init_kwargs = kwargs
            self.messages = types.SimpleNamespace(create=create)

    module.Anthropic = Anthropic
    return module


def text_response(text):
    return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)])


class ApiClientTests(unittest.TestCase):
    def call_with(self, create):
        module = fake_anthropic_module(create)
        with mock.patch.dict(sys.modules, {"anthropic": module}):
            client = AnthropicClient("sk-test-secret-key")
            return client.complete("system", "user"), module

    def raising(self, name):
        holder = {}

        def create(**kwargs):
            raise getattr(holder["module"], name)("raw provider message with sk-test-secret-key")

        module = fake_anthropic_module(create)
        holder["module"] = module
        return module

    def error_for(self, name):
        module = self.raising(name)
        with mock.patch.dict(sys.modules, {"anthropic": module}):
            client = AnthropicClient("sk-test-secret-key")
            with self.assertRaises(AIServiceError) as ctx:
                client.complete("s", "u")
        return ctx.exception

    def test_successful_call_returns_text_and_uses_config(self):
        text, module = self.call_with(lambda **kw: text_response("  hello  "))
        self.assertEqual(text, "hello")
        self.assertEqual(module.init_kwargs["api_key"], "sk-test-secret-key")
        self.assertIn("max_retries", module.init_kwargs)

    def test_rate_limit_gives_friendly_message(self):
        err = self.error_for("RateLimitError")
        self.assertIn("rate limit", str(err).lower())

    def test_timeout_and_connection_errors_are_different_messages(self):
        timeout = str(self.error_for("APITimeoutError"))
        connection = str(self.error_for("APIConnectionError"))
        self.assertIn("too long", timeout)
        self.assertIn("internet", connection)

    def test_bad_key_is_reported_as_unavailable(self):
        self.assertIsInstance(self.error_for("AuthenticationError"), AIUnavailableError)

    def test_other_api_errors_are_handled(self):
        self.assertIsInstance(self.error_for("APIStatusError"), AIServiceError)
        self.assertIsInstance(self.error_for("BadRequestError"), AIServiceError)

    def test_error_messages_never_leak_the_api_key_or_raw_text(self):
        for name in ("RateLimitError", "AuthenticationError", "APITimeoutError", "APIStatusError"):
            self.assertNotIn("sk-test", str(self.error_for(name)))

    def test_unexpected_exception_is_wrapped(self):
        def create(**kwargs):
            raise RuntimeError("boom sk-test-secret-key")

        with mock.patch.dict(sys.modules, {"anthropic": fake_anthropic_module(create)}):
            with self.assertRaises(AIServiceError) as ctx:
                AnthropicClient("k").complete("s", "u")
        self.assertNotIn("sk-test", str(ctx.exception))

    def test_empty_model_reply_is_an_error_not_a_blank_answer(self):
        with mock.patch.dict(sys.modules, {"anthropic": fake_anthropic_module(lambda **kw: text_response("  "))}):
            with self.assertRaises(AIServiceError):
                AnthropicClient("k").complete("s", "u")

    def test_missing_sdk_gives_install_hint(self):
        with mock.patch.dict(sys.modules, {"anthropic": None}):  # makes `import anthropic` fail
            with self.assertRaises(AIUnavailableError) as ctx:
                AnthropicClient("k")
        self.assertIn("pip install", str(ctx.exception))


class MissingApiKeyTests(unittest.TestCase):
    def test_get_client_without_key_raises_helpful_error(self):
        with mock.patch("src.ai_service.config.get_api_key", return_value=None):
            with self.assertRaises(AIUnavailableError) as ctx:
                get_client()
        self.assertIn(".env", str(ctx.exception))

    def test_placeholder_key_counts_as_missing(self):
        from src import config

        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "your-api-key-here"}):
            self.assertIsNone(config.get_api_key())
            self.assertFalse(config.api_key_available())

    def test_blank_and_real_looking_keys(self):
        from src import config

        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "   "}):
            self.assertFalse(config.api_key_available())
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-realistic"}):
            self.assertTrue(config.api_key_available())


if __name__ == "__main__":
    unittest.main()
