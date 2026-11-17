"""Step 4 of ingestion: turn each chunk into an embedding.

An embedding is a list of 768 numbers that captures what a piece of text
*means*. Texts about similar ideas get similar numbers, like nearby points on
a map, so "photosynthesis in leaves" lands near "how plants make food".
"""

from __future__ import annotations

from typing import Callable, Sequence

from app.llm.base import LLMError, LLMProvider

BATCH = 100


def embed_texts(
    llm: LLMProvider,
    texts: Sequence[str],
    titles: Sequence[str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        batch = list(texts[start : start + BATCH])
        batch_titles = list(titles[start : start + BATCH]) if titles else None
        out = llm.embed(batch, task="document", titles=batch_titles)
        if len(out) != len(batch) or any(len(v) != llm.dim for v in out):
            raise LLMError("Embedding size mismatch; check GEMINI_EMBED_DIM matches the database (768)")
        vectors.extend(out)
        if on_progress:
            on_progress(len(vectors), len(texts))
    return vectors
