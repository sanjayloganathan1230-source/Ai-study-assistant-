"""Tests for src/retrieval.py

Uses the real sample notes (sample_notes.txt), so retrieval quality is checked on
realistic study text. No API key or internet is needed.
"""

import unittest
from pathlib import Path

import numpy as np

from src.chunker import Chunk, chunk_pages
from src.pdf_processor import PageText
from src.retrieval import (
    TfidfEmbedder,
    VectorStore,
    analyze,
    get_embedder,
)

SAMPLE_TXT = Path(__file__).resolve().parent.parent / "sample_data" / "sample_notes.txt"


def sample_store(chunk_size=500, overlap=80) -> VectorStore:
    raw = SAMPLE_TXT.read_text(encoding="utf-8")
    blocks = [b.strip() for b in raw.split("=== PAGE ===") if b.strip()]
    pages = [PageText(i + 1, b) for i, b in enumerate(blocks)]
    store = VectorStore()
    store.build(chunk_pages(pages, chunk_size, overlap))
    return store


class AnalyzeTests(unittest.TestCase):
    def test_lowercases_and_removes_stop_words(self):
        self.assertEqual(analyze("The Model IS Learning"), ["model", "learn"])

    def test_stemming_matches_word_forms(self):
        self.assertEqual(analyze("overfitting")[0], analyze("overfit")[0])
        self.assertEqual(analyze("models")[0], analyze("model")[0])

    def test_short_words_are_not_over_stemmed(self):
        self.assertEqual(analyze("bias"), ["bias"])

    def test_empty_text(self):
        self.assertEqual(analyze(""), [])


class EmbedderTests(unittest.TestCase):
    def test_embeddings_have_one_row_per_text(self):
        emb = TfidfEmbedder()
        matrix = emb.fit(["cats like fish", "dogs like bones", "birds fly south"])
        self.assertEqual(matrix.shape[0], 3)
        self.assertEqual(emb.embed(["cats"]).shape, (1, matrix.shape[1]))

    def test_text_with_only_stop_words_does_not_crash(self):
        emb = TfidfEmbedder()
        matrix = emb.fit(["the and of", "is it a"])
        self.assertEqual(matrix.shape[0], 2)
        self.assertEqual(float(np.abs(emb.embed(["the"])).sum()), 0.0)

    def test_unknown_embedder_name_raises(self):
        with self.assertRaises(ValueError):
            get_embedder("magic")


class VectorStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = sample_store()

    def top_page(self, question):
        results = self.store.search(question)
        self.assertTrue(results, f"no results for: {question}")
        return results[0].page_number

    def test_store_has_chunks_from_all_pages(self):
        self.assertEqual({c.page_number for c in self.store.chunks}, {1, 2, 3})

    def test_finds_page_for_supervised_learning(self):
        self.assertEqual(self.top_page("What is supervised learning?"), 1)

    def test_finds_page_for_overfitting(self):
        self.assertEqual(self.top_page("Explain overfitting"), 2)

    def test_finds_page_for_cross_validation(self):
        self.assertEqual(self.top_page("How does cross-validation work?"), 2)

    def test_finds_page_for_precision_and_recall(self):
        self.assertEqual(self.top_page("What are precision and recall?"), 3)

    def test_finds_page_for_missing_values(self):
        self.assertEqual(self.top_page("How do we handle missing values?"), 3)

    def test_top_result_text_contains_the_answer(self):
        best = self.store.search("What is K-means clustering?")[0]
        self.assertIn("K-means", best.text)

    def test_results_are_sorted_best_first(self):
        scores = [r.score for r in self.store.search("training and test set split", top_k=4)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_limits_number_of_results(self):
        self.assertLessEqual(len(self.store.search("model data learning", top_k=2)), 2)

    def test_scores_stay_between_zero_and_one(self):
        for result in self.store.search("machine learning model", top_k=10, min_score=0.0):
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 1.0 + 1e-6)

    def test_unrelated_question_returns_nothing(self):
        # Nothing in the notes is about cooking, so retrieval must come back empty.
        self.assertEqual(self.store.search("What is the best recipe for chocolate cake?"), [])

    def test_gibberish_and_empty_queries_return_nothing(self):
        self.assertEqual(self.store.search("zzzzqqq xxyyzz"), [])
        self.assertEqual(self.store.search(""), [])
        self.assertEqual(self.store.search("   "), [])

    def test_min_score_can_be_raised_to_be_stricter(self):
        strict = self.store.search("What is supervised learning?", min_score=0.99)
        self.assertEqual(strict, [])

    def test_top_k_zero_returns_nothing(self):
        self.assertEqual(self.store.search("machine learning", top_k=0), [])


class EmptyAndSmallStoreTests(unittest.TestCase):
    def test_empty_store_returns_nothing(self):
        store = VectorStore()
        store.build([])
        self.assertEqual(len(store), 0)
        self.assertEqual(store.search("anything"), [])

    def test_search_before_build_returns_nothing(self):
        self.assertEqual(VectorStore().search("anything"), [])

    def test_single_chunk_store_works(self):
        store = VectorStore()
        store.build([Chunk(0, 5, "Photosynthesis converts sunlight into chemical energy.")])
        results = store.search("How does photosynthesis work?")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].page_number, 5)

    def test_rebuilding_replaces_old_content(self):
        store = VectorStore()
        store.build([Chunk(0, 1, "Volcanoes erupt molten lava and ash.")])
        store.build([Chunk(0, 2, "Glaciers are slow rivers of ice.")])
        self.assertEqual(store.search("volcano lava"), [])
        self.assertEqual(store.search("glacier ice")[0].page_number, 2)


class SpreadSampleTests(unittest.TestCase):
    def make_store(self, n):
        store = VectorStore()
        store.build([Chunk(i, i + 1, f"Topic{i} has unique words{i} about subject{i}.") for i in range(n)])
        return store

    def test_returns_everything_when_small(self):
        self.assertEqual(len(self.make_store(3).spread_sample(10)), 3)

    def test_samples_evenly_across_document(self):
        picked = self.make_store(100).spread_sample(5)
        self.assertEqual([c.chunk_id for c in picked], [0, 20, 40, 60, 80])

    def test_zero_or_negative_returns_empty(self):
        self.assertEqual(self.make_store(5).spread_sample(0), [])


if __name__ == "__main__":
    unittest.main()
