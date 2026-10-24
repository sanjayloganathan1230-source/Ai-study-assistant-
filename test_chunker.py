"""Tests for src/chunker.py"""

import re
import unittest

from src.chunker import chunk_pages, split_text
from src.pdf_processor import PageText


def numbered_sentences(count: int) -> str:
    return " ".join(f"Sentence number {i} is here." for i in range(count))


def sentences_in(chunk: str) -> set:
    """Pull out whole sentences like 'Sentence number 7 is here.' from a chunk."""
    return set(re.findall(r"Sentence number \d+ is here\.", chunk))


class SplitTextTests(unittest.TestCase):
    def test_short_text_gives_one_chunk(self):
        chunks = split_text("Machine learning is fun. It uses data.", chunk_size=500, overlap=50)
        self.assertEqual(chunks, ["Machine learning is fun. It uses data."])

    def test_empty_text_gives_no_chunks(self):
        self.assertEqual(split_text("", chunk_size=100, overlap=10), [])
        self.assertEqual(split_text("   \n\n  ", chunk_size=100, overlap=10), [])

    def test_chunks_never_exceed_chunk_size(self):
        chunks = split_text(numbered_sentences(60), chunk_size=100, overlap=40)
        self.assertGreater(len(chunks), 3)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 100)

    def test_neighbouring_chunks_overlap(self):
        chunks = split_text(numbered_sentences(30), chunk_size=100, overlap=40)
        self.assertGreater(len(chunks), 2)
        for first, second in zip(chunks, chunks[1:]):
            self.assertTrue(
                sentences_in(first) & sentences_in(second),
                "neighbouring chunks should share at least one sentence",
            )

    def test_zero_overlap_means_no_shared_sentences(self):
        chunks = split_text(numbered_sentences(30), chunk_size=100, overlap=0)
        self.assertGreater(len(chunks), 2)
        for first, second in zip(chunks, chunks[1:]):
            self.assertTrue(sentences_in(first), "helper must find sentences, or this test proves nothing")
            self.assertFalse(sentences_in(first) & sentences_in(second))

    def test_no_sentence_is_lost(self):
        text = numbered_sentences(40)
        joined = " ".join(split_text(text, chunk_size=100, overlap=40))
        for i in range(40):
            self.assertIn(f"Sentence number {i} is here.", joined)

    def test_very_long_word_is_split_safely(self):
        chunks = split_text("x" * 250, chunk_size=100, overlap=10)
        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(len(c) <= 100 for c in chunks))

    def test_long_sentence_without_punctuation_is_split(self):
        chunks = split_text("word " * 100, chunk_size=80, overlap=10)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 80 for c in chunks))

    def test_invalid_settings_raise_value_error(self):
        with self.assertRaises(ValueError):
            split_text("hello", chunk_size=0, overlap=0)
        with self.assertRaises(ValueError):
            split_text("hello", chunk_size=100, overlap=100)
        with self.assertRaises(ValueError):
            split_text("hello", chunk_size=100, overlap=-1)


class ChunkPagesTests(unittest.TestCase):
    def test_page_numbers_are_kept(self):
        pages = [
            PageText(1, "First page about cats. " * 20),
            PageText(3, "Third page about dogs. " * 20),
        ]
        chunks = chunk_pages(pages, chunk_size=120, overlap=20)
        self.assertEqual({c.page_number for c in chunks}, {1, 3})
        for chunk in chunks:
            if chunk.page_number == 1:
                self.assertIn("cats", chunk.text)
                self.assertNotIn("dogs", chunk.text)
            else:
                self.assertIn("dogs", chunk.text)

    def test_chunk_ids_are_sequential_from_zero(self):
        pages = [PageText(1, numbered_sentences(20)), PageText(2, numbered_sentences(20))]
        chunks = chunk_pages(pages, chunk_size=100, overlap=20)
        self.assertEqual([c.chunk_id for c in chunks], list(range(len(chunks))))

    def test_no_pages_gives_no_chunks(self):
        self.assertEqual(chunk_pages([]), [])


if __name__ == "__main__":
    unittest.main()
