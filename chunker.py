"""Split page text into small pieces called "chunks".

Why chunk?
    An AI model can only read a limited amount of text at once, and searching
    works better on small focused pieces than on a whole 100-page document.

How we chunk:
    * Every chunk comes from ONE page, so we always know the exact page number
      to show as the source.
    * We split on sentence boundaries so sentences are not cut in half.
    * Neighbouring chunks share a little text ("overlap") so an idea that sits
      at the edge of a chunk is not lost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src import config
from src.pdf_processor import PageText

# Split after . ! ? followed by space, or at any line break.
_UNIT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class Chunk:
    chunk_id: int      # 0, 1, 2, ... across the whole document
    page_number: int   # which PDF page this text came from
    text: str


def _joined_len(parts: list[str]) -> int:
    """Length of the parts if joined with single spaces."""
    return sum(len(p) for p in parts) + max(len(parts) - 1, 0)


def _split_long_unit(unit: str, size: int) -> list[str]:
    """Break one over-long sentence into pieces of at most `size` characters."""
    pieces: list[str] = []
    line = ""
    for word in unit.split():
        if len(word) > size:  # a single giant word (e.g. a long URL)
            if line:
                pieces.append(line)
                line = ""
            pieces.extend(word[i : i + size] for i in range(0, len(word), size))
            continue
        candidate = f"{line} {word}".strip()
        if len(candidate) > size:
            pieces.append(line)
            line = word
        else:
            line = candidate
    if line:
        pieces.append(line)
    return pieces


def _to_units(text: str, size: int) -> list[str]:
    units: list[str] = []
    for part in _UNIT_SPLIT.split(text):
        part = part.strip()
        if not part:
            continue
        if len(part) > size:
            units.extend(_split_long_unit(part, size))
        else:
            units.append(part)
    return units


def _overlap_tail(parts: list[str], overlap: int) -> list[str]:
    """The last few sentences of a finished chunk, up to `overlap` characters."""
    if overlap <= 0:
        return []
    tail: list[str] = []
    for part in reversed(parts):
        if _joined_len([part] + tail) > overlap:
            break
        tail.insert(0, part)
    return tail


def split_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split one block of text into chunks of at most `chunk_size` characters."""
    chunk_size = config.CHUNK_SIZE if chunk_size is None else chunk_size
    overlap = config.CHUNK_OVERLAP if overlap is None else overlap
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be 0 or more, and smaller than chunk_size")

    chunks: list[str] = []
    current: list[str] = []
    for unit in _to_units(text, chunk_size):
        if current and _joined_len(current + [unit]) > chunk_size:
            chunks.append(" ".join(current))
            current = _overlap_tail(current, overlap)
            if current and _joined_len(current + [unit]) > chunk_size:
                current = []  # overlap would make the chunk too big, so skip it
        current.append(unit)
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_pages(
    pages: list[PageText], chunk_size: int | None = None, overlap: int | None = None
) -> list[Chunk]:
    """Chunk every page and number the chunks across the whole document."""
    result: list[Chunk] = []
    for page in pages:
        for piece in split_text(page.text, chunk_size, overlap):
            result.append(Chunk(chunk_id=len(result), page_number=page.page_number, text=piece))
    return result
