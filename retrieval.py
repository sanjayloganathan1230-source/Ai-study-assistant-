"""Embeddings and vector search: find the chunks that best match a question.

Big idea (RAG retrieval):
    1. EMBED  - turn every chunk of text into a vector (a list of numbers).
    2. STORE  - keep all the vectors together (our "vector store").
    3. SEARCH - turn the question into a vector too, then find the chunks whose
                vectors point in the most similar direction (cosine similarity).

Which embedding method?
    * TfidfEmbedder (default): runs locally, offline, no API key. It scores words
      by how important they are (rare words count more than common ones). It
      matches on shared WORDS, so it can miss synonyms ("car" vs "automobile").
    * SentenceTransformerEmbedder (optional): a neural model that understands
      meaning better. It needs `pip install sentence-transformers` and a one-time
      model download, so it is not used unless you ask for it.

Both have the same two methods (fit / embed), so the rest of the app does not
care which one is used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from src import config
from src.chunker import Chunk

# Below this similarity a chunk is considered "not related" to the question.
# This is what lets the app say "not found in your notes" instead of guessing.
DEFAULT_MIN_SCORE = 0.08

_WORD = re.compile(r"[a-z0-9]+")
_SUFFIXES = ("ing", "ed", "es", "s")


def _stem(word: str) -> str:
    """Very light stemming so 'overfitting', 'overfit' and 'overfits' match."""
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            stem = word[: -len(suffix)]
            # "overfitting" -> "overfitt": drop the doubled letter so it equals "overfit"
            if suffix in ("ing", "ed") and stem[-1] == stem[-2] and stem[-1] not in "lsz":
                stem = stem[:-1]
            return stem
    return word


def analyze(text: str) -> list[str]:
    """Lowercase -> split into words -> drop filler words -> light stemming."""
    words = _WORD.findall(text.lower())
    return [_stem(w) for w in words if w not in ENGLISH_STOP_WORDS and len(w) > 1]


class TfidfEmbedder:
    """Local keyword-weighted embeddings (no internet, no API key)."""

    name = "tfidf"

    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(analyzer=analyze, sublinear_tf=True)
        self._fitted = False

    def fit(self, texts: list[str]) -> np.ndarray:
        """Learn the vocabulary from the document's chunks and embed them."""
        try:
            matrix = self._vectorizer.fit_transform(texts)
        except ValueError:  # no usable words at all (e.g. only stop words)
            self._fitted = False
            return np.zeros((len(texts), 1), dtype=np.float32)
        self._fitted = True
        return matrix.toarray().astype(np.float32)

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed new text (such as a question) using the learned vocabulary."""
        if not self._fitted:
            return np.zeros((len(texts), 1), dtype=np.float32)
        return self._vectorizer.transform(texts).toarray().astype(np.float32)


class SentenceTransformerEmbedder:
    """Optional neural embeddings. Needs: pip install sentence-transformers"""

    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install it first: pip install sentence-transformers") from exc
        self._model = SentenceTransformer(model_name)

    def fit(self, texts: list[str]) -> np.ndarray:
        return self.embed(texts)

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True), dtype=np.float32)


def get_embedder(kind: str = "tfidf"):
    """Pick an embedder by name."""
    if kind == "tfidf":
        return TfidfEmbedder()
    if kind in ("sentence-transformers", "neural"):
        return SentenceTransformerEmbedder()
    raise ValueError(f"Unknown embedder: {kind!r}")


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """Scale every vector to length 1, so a plain dot product equals cosine similarity."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # all-zero vectors stay zero (their similarity is 0)
    return vectors / norms


@dataclass
class SearchResult:
    chunk: Chunk
    score: float  # cosine similarity, 0 (unrelated) to 1 (very similar)

    @property
    def page_number(self) -> int:
        return self.chunk.page_number

    @property
    def text(self) -> str:
        return self.chunk.text


class VectorStore:
    """Holds the chunks of ONE document and their vectors, in memory only."""

    def __init__(self, embedder=None) -> None:
        self.embedder = embedder or TfidfEmbedder()
        self.chunks: list[Chunk] = []
        self._vectors = np.zeros((0, 1), dtype=np.float32)

    def __len__(self) -> int:
        return len(self.chunks)

    def build(self, chunks: list[Chunk]) -> None:
        """Embed all chunks and remember them."""
        self.chunks = list(chunks)
        if not self.chunks:
            self._vectors = np.zeros((0, 1), dtype=np.float32)
            return
        self._vectors = _normalize(self.embedder.fit([c.text for c in self.chunks]))

    def search(
        self, query: str, top_k: int | None = None, min_score: float = DEFAULT_MIN_SCORE
    ) -> list[SearchResult]:
        """Return up to `top_k` chunks most similar to `query`, best first.

        Chunks scoring below `min_score` are dropped, so an unrelated question
        can return an EMPTY list. The AI step then says "not in the notes".
        """
        top_k = config.TOP_K if top_k is None else top_k
        if not self.chunks or not query.strip() or top_k <= 0:
            return []

        query_vec = _normalize(self.embedder.embed([query]))
        if query_vec.shape[1] != self._vectors.shape[1]:
            return []
        scores = (self._vectors @ query_vec[0]).astype(float)

        # Highest scores first; on a tie the earlier chunk wins (stable order).
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [
            SearchResult(self.chunks[i], float(scores[i]))
            for i in order[:top_k]
            if scores[i] >= min_score
        ]

    def spread_sample(self, max_chunks: int) -> list[Chunk]:
        """Pick chunks evenly across the whole document (used for summaries/quizzes)."""
        if max_chunks <= 0 or not self.chunks:
            return []
        if len(self.chunks) <= max_chunks:
            return list(self.chunks)
        step = len(self.chunks) / max_chunks
        return [self.chunks[int(i * step)] for i in range(max_chunks)]
