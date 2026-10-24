"""Check what the AI sends back before the app trusts it.

An AI model returns TEXT. We ask it for JSON (a structured format), but it can
still return broken JSON, 3 options instead of 4, an answer that matches no
option, and so on. These functions parse and validate the reply, drop bad items,
and raise ValidationError if nothing usable is left. Nothing here talks to the
internet, so it is easy to test.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass

LETTERS = "ABCD"
_OPTION_PREFIX = re.compile(r"^\s*\(?[A-Da-d][\).:]\s+")
_LETTER_ONLY = re.compile(r"^\s*\(?([A-Da-d])[\).:]?\s*$")
_LETTER_THEN_TEXT = re.compile(r"^\s*\(?([A-Da-d])[\).:]\s+")

MAX_QUESTION_CHARS = 500
MAX_OPTION_CHARS = 300
MAX_EXPLANATION_CHARS = 600
MAX_CARD_CHARS = 600


class ValidationError(ValueError):
    """The AI reply could not be turned into valid study material."""


@dataclass
class QuizQuestion:
    question: str
    options: list[str]      # always exactly 4
    correct_index: int      # 0-3
    explanation: str
    page: int | None = None

    @property
    def correct_letter(self) -> str:
        return LETTERS[self.correct_index]

    @property
    def correct_text(self) -> str:
        return self.options[self.correct_index]


@dataclass
class Flashcard:
    front: str
    back: str
    page: int | None = None


# ------------------------------------------------------------------ JSON parsing
def extract_json(text: str):
    """Pull JSON out of a model reply (it may add ```json fences or extra words)."""
    if not text or not text.strip():
        raise ValidationError("The AI returned an empty reply.")
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValidationError("The AI reply was not valid JSON.")


def _as_list(data, keys: tuple[str, ...]) -> list:
    """Accept either a bare list or an object that wraps the list."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            if isinstance(data.get(key), list):
                return data[key]
    raise ValidationError("The AI reply did not contain a list of items.")


def _clean(value, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _page_or_none(value) -> int | None:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


# ------------------------------------------------------------------------- quiz
def _find_correct_index(answer, options: list[str]) -> int | None:
    """Work out which of the 4 options is correct from the model's `answer` field."""
    if isinstance(answer, bool):
        return None
    if isinstance(answer, int):
        return answer if 0 <= answer < 4 else None
    if not isinstance(answer, str) or not answer.strip():
        return None
    match = _LETTER_ONLY.match(answer) or _LETTER_THEN_TEXT.match(answer)
    if match:
        return LETTERS.index(match.group(1).upper())
    wanted = _clean(_OPTION_PREFIX.sub("", answer), MAX_OPTION_CHARS).lower()
    for i, option in enumerate(options):
        if option.lower() == wanted:
            return i
    return None


def _validate_one_question(item) -> QuizQuestion | None:
    if not isinstance(item, dict):
        return None
    question = _clean(item.get("question"), MAX_QUESTION_CHARS)
    raw_options = item.get("options")
    if not question or not isinstance(raw_options, list) or len(raw_options) != 4:
        return None
    options = [_clean(_OPTION_PREFIX.sub("", o) if isinstance(o, str) else "", MAX_OPTION_CHARS)
               for o in raw_options]
    if any(not o for o in options) or len({o.lower() for o in options}) != 4:
        return None  # empty or duplicate options
    index = _find_correct_index(item.get("answer"), options)
    if index is None:
        return None
    explanation = _clean(item.get("explanation"), MAX_EXPLANATION_CHARS)
    if not explanation:
        return None
    return QuizQuestion(question, options, index, explanation, _page_or_none(item.get("page")))


def validate_quiz(data, max_questions: int = 15, shuffle: bool = False,
                  rng: random.Random | None = None) -> tuple[list[QuizQuestion], int]:
    """Return (valid_questions, number_skipped). Raises ValidationError if none are valid.

    A question is valid only if it has: question text, exactly 4 distinct options,
    a correct answer that matches one of them, and a short explanation.
    `shuffle=True` mixes the option order (models like to put the answer first).
    """
    items = _as_list(data, ("questions", "quiz", "items"))
    valid: list[QuizQuestion] = []
    seen: set[str] = set()
    for item in items:
        q = _validate_one_question(item)
        if q is None or q.question.lower() in seen:
            continue
        seen.add(q.question.lower())
        valid.append(q)
        if len(valid) >= max_questions:
            break
    skipped = len(items) - len(valid)
    if not valid:
        raise ValidationError("None of the generated questions were valid.")
    if shuffle:
        rng = rng or random.Random()
        for q in valid:
            correct = q.options[q.correct_index]
            rng.shuffle(q.options)
            q.correct_index = q.options.index(correct)
    return valid, skipped


def score_answers(questions: list[QuizQuestion], chosen: list[int | None]) -> int:
    """Count correct answers. `chosen[i]` is the picked option index (or None = unanswered)."""
    return sum(
        1 for q, pick in zip(questions, chosen) if pick is not None and pick == q.correct_index
    )


# -------------------------------------------------------------------- flashcards
def validate_flashcards(data, max_cards: int = 30) -> tuple[list[Flashcard], int]:
    """Return (valid_cards, number_skipped). Raises ValidationError if none are valid."""
    items = _as_list(data, ("flashcards", "cards", "items"))
    cards: list[Flashcard] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        front = _clean(item.get("front") or item.get("question"), MAX_CARD_CHARS)
        back = _clean(item.get("back") or item.get("answer"), MAX_CARD_CHARS)
        if not front or not back or front.lower() in seen:
            continue
        seen.add(front.lower())
        cards.append(Flashcard(front, back, _page_or_none(item.get("page"))))
        if len(cards) >= max_cards:
            break
    skipped = len(items) - len(cards)
    if not cards:
        raise ValidationError("None of the generated flashcards were valid.")
    return cards, skipped
