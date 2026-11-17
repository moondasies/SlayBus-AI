"""Step 3 of ingestion: cut each chapter into overlapping chunks.

Why chunks? The AI can only read so much at once, and search works best on
small focused pieces. Think of cutting a book into index cards (~600 tokens,
about 2 paragraphs). Neighbouring cards share a little text (the "overlap")
so an idea that sits on a cut line is not lost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingest.pdf_reader import Page

CHARS_PER_TOKEN = 4  # good-enough estimate for English text


@dataclass
class Chunk:
    page: int
    content: str
    token_count: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _units(pages: list[Page], max_chars: int) -> list[tuple[int, str, bool]]:
    """Split pages into sentence-sized units: (page, text, starts_new_paragraph).

    Small units matter: overlap is made of whole units, so they must be
    smaller than the overlap budget.
    """
    units: list[tuple[int, str, bool]] = []
    for page in pages:
        for para in re.split(r"\n\s*\n", page.text):
            para = re.sub(r"\s*\n\s*", " ", para).strip()
            if not para:
                continue
            first = True
            for sent in re.split(r"(?<=[.!?])\s+", para):
                while len(sent) > max_chars:  # absurdly long "sentence": hard split
                    units.append((page.number, sent[:max_chars], first))
                    sent, first = sent[max_chars:], False
                if sent:
                    units.append((page.number, sent, first))
                    first = False
    return units


def chunk_pages(pages: list[Page], chunk_tokens: int = 600, overlap_tokens: int = 100) -> list[Chunk]:
    max_chars = chunk_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN
    units = _units(pages, max_chars)

    chunks: list[Chunk] = []
    current: list[tuple[int, str, bool]] = []
    size = 0
    new_since_emit = False

    def emit() -> None:
        text = "".join((("\n\n" if new_para else " ") if i else "") + t for i, (_, t, new_para) in enumerate(current))
        chunks.append(Chunk(page=current[0][0], content=text, token_count=estimate_tokens(text)))

    for unit in units:
        if current and size + len(unit[1]) > max_chars:
            emit()
            # carry the tail of this chunk into the next one (overlap)
            tail, tail_size = [], 0
            for u in reversed(current):
                if tail_size + len(u[1]) > overlap_chars:
                    break
                tail.insert(0, u)
                tail_size += len(u[1])
            current, size = tail, tail_size
            new_since_emit = False
        current.append(unit)
        size += len(unit[1])
        new_since_emit = True

    if current and new_since_emit:
        emit()
    # drop near-empty scraps (e.g. a lone figure caption)
    return [c for c in chunks if len(c.content) >= 80] or chunks
