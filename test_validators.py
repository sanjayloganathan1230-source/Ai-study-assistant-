"""Tests for src/validators.py (quiz and flashcard validation)."""

import json
import random
import unittest

from src.validators import (
    QuizQuestion,
    ValidationError,
    extract_json,
    score_answers,
    validate_flashcards,
    validate_quiz,
)


def good_question(**overrides):
    item = {
        "question": "What does supervised learning use?",
        "options": ["Labelled examples", "No data", "Only rewards", "Random noise"],
        "answer": "A",
        "explanation": "Supervised learning learns from labelled examples.",
        "page": 1,
    }
    item.update(overrides)
    return item


class ExtractJsonTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(extract_json('[{"a": 1}]'), [{"a": 1}])

    def test_json_inside_code_fence(self):
        self.assertEqual(extract_json('```json\n[{"a": 1}]\n```'), [{"a": 1}])

    def test_json_surrounded_by_chatty_text(self):
        self.assertEqual(extract_json('Sure! Here you go:\n[{"a": 1}]\nHope it helps.'), [{"a": 1}])

    def test_invalid_json_raises(self):
        with self.assertRaises(ValidationError):
            extract_json("this is not json at all")

    def test_empty_reply_raises(self):
        with self.assertRaises(ValidationError):
            extract_json("   ")


class ValidateQuizTests(unittest.TestCase):
    def test_valid_question_is_accepted(self):
        questions, skipped = validate_quiz([good_question()])
        self.assertEqual(skipped, 0)
        q = questions[0]
        self.assertEqual(len(q.options), 4)
        self.assertEqual(q.correct_text, "Labelled examples")
        self.assertEqual(q.correct_letter, "A")
        self.assertEqual(q.page, 1)

    def test_wrapped_in_object_is_accepted(self):
        questions, _ = validate_quiz({"questions": [good_question()]})
        self.assertEqual(len(questions), 1)

    def test_must_have_exactly_four_options(self):
        for options in (["a", "b", "c"], ["a", "b", "c", "d", "e"], []):
            with self.assertRaises(ValidationError):
                validate_quiz([good_question(options=options)])

    def test_duplicate_options_are_rejected(self):
        with self.assertRaises(ValidationError):
            validate_quiz([good_question(options=["Same", "same", "Other", "Another"])])

    def test_empty_option_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_quiz([good_question(options=["A thing", "", "Other", "Another"])])

    def test_answer_must_match_an_option(self):
        for bad in ("E", "", None, "Something not listed", 7, True):
            with self.assertRaises(ValidationError, msg=f"answer={bad!r}"):
                validate_quiz([good_question(answer=bad)])

    def test_answer_formats_are_understood(self):
        expected = {"B": 1, "b": 1, "(C)": 2, "D.": 3, "B) Only rewards": 1, "Labelled examples": 0,
                    "labelled examples": 0, 2: 2}
        for answer, index in expected.items():
            questions, _ = validate_quiz([good_question(answer=answer)])
            self.assertEqual(questions[0].correct_index, index, msg=f"answer={answer!r}")

    def test_option_letter_prefixes_are_removed(self):
        q = good_question(options=["A) Labelled examples", "B) No data", "C. Only rewards", "D: Random noise"])
        questions, _ = validate_quiz([q])
        self.assertEqual(questions[0].options[0], "Labelled examples")
        self.assertEqual(questions[0].options[3], "Random noise")

    def test_missing_explanation_or_question_is_rejected(self):
        for field in ("explanation", "question"):
            with self.assertRaises(ValidationError):
                validate_quiz([good_question(**{field: ""})])

    def test_bad_items_are_skipped_but_good_ones_kept(self):
        data = [good_question(), "garbage", good_question(question="Second?", options=["x", "y"]),
                good_question(question="Third question?")]
        questions, skipped = validate_quiz(data)
        self.assertEqual(len(questions), 2)
        self.assertEqual(skipped, 2)

    def test_duplicate_questions_are_removed(self):
        questions, _ = validate_quiz([good_question(), good_question()])
        self.assertEqual(len(questions), 1)

    def test_max_questions_is_respected(self):
        data = [good_question(question=f"Question {i}?") for i in range(10)]
        questions, _ = validate_quiz(data, max_questions=3)
        self.assertEqual(len(questions), 3)

    def test_invalid_page_becomes_none(self):
        questions, _ = validate_quiz([good_question(page="unknown")])
        self.assertIsNone(questions[0].page)

    def test_not_a_list_raises(self):
        with self.assertRaises(ValidationError):
            validate_quiz({"message": "no questions here"})

    def test_shuffle_keeps_the_correct_answer_correct(self):
        data = [good_question(question=f"Question {i}?") for i in range(20)]
        questions, _ = validate_quiz(data, shuffle=True, rng=random.Random(1))
        self.assertTrue(all(q.correct_text == "Labelled examples" for q in questions))
        self.assertTrue(all(len(set(q.options)) == 4 for q in questions))
        # With 20 questions, shuffling should move the answer away from position A at least once.
        self.assertTrue(any(q.correct_index != 0 for q in questions))


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.questions = [
            QuizQuestion("Q1", ["a", "b", "c", "d"], 0, "e"),
            QuizQuestion("Q2", ["a", "b", "c", "d"], 2, "e"),
            QuizQuestion("Q3", ["a", "b", "c", "d"], 3, "e"),
        ]

    def test_all_correct(self):
        self.assertEqual(score_answers(self.questions, [0, 2, 3]), 3)

    def test_some_wrong_and_unanswered(self):
        self.assertEqual(score_answers(self.questions, [0, 1, None]), 1)

    def test_nothing_answered(self):
        self.assertEqual(score_answers(self.questions, [None, None, None]), 0)


class FlashcardValidationTests(unittest.TestCase):
    def test_valid_cards(self):
        cards, skipped = validate_flashcards([{"front": "What is ML?", "back": "Learning from data", "page": 1}])
        self.assertEqual((len(cards), skipped), (1, 0))
        self.assertEqual(cards[0].back, "Learning from data")

    def test_question_answer_keys_are_accepted(self):
        cards, _ = validate_flashcards({"cards": [{"question": "Q?", "answer": "A."}]})
        self.assertEqual(cards[0].front, "Q?")

    def test_incomplete_and_duplicate_cards_are_skipped(self):
        data = [{"front": "One", "back": "1"}, {"front": "Two", "back": ""}, {"front": "one", "back": "dup"}, 5]
        cards, skipped = validate_flashcards(data)
        self.assertEqual(len(cards), 1)
        self.assertEqual(skipped, 3)

    def test_no_valid_cards_raises(self):
        with self.assertRaises(ValidationError):
            validate_flashcards([{"front": "", "back": ""}])

    def test_round_trip_through_json_text(self):
        reply = "```json\n" + json.dumps([{"front": "F", "back": "B"}]) + "\n```"
        cards, _ = validate_flashcards(extract_json(reply))
        self.assertEqual(cards[0].front, "F")


if __name__ == "__main__":
    unittest.main()
