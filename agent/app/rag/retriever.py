"""Retrieval: pick the textbook chunks the AI should read for a question set.

Two ideas mixed together:
- **Relevance**: vector search (match_chunks) finds the chunks closest in
  meaning to "key ideas of <chapter> for <question type>".
- **Spread**: we also sample chunks evenly from the start, middle and end of
  the chapter, so questions are not all from page 1.
Chunks that earlier question sets already used are pushed to the back, so
one paper covers more of the chapter.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app import db
from app.generate.schemas import TYPE_LABELS
from app.llm.base import LLMProvider, SourceChunk


@dataclass
class ChunkUsage:
    """Remembers how often each chunk has been used while building one paper."""

    counts: Counter = field(default_factory=Counter)

    def mark(self, chunk_ids: list[str]) -> None:
        self.counts.update(chunk_ids)


def _evenly_spaced(items: list, k: int, offset: int = 0) -> list:
    if k <= 0 or not items:
        return []
    if len(items) <= k:
        return list(items)
    step = len(items) / k
    return [items[(int(i * step) + offset) % len(items)] for i in range(k)]


def retrieve_for_chapter(
    llm: LLMProvider,
    textbook_id: str,
    chapter_id: str,
    chapter_title: str,
    qtype: str,
    k: int,
    usage: ChunkUsage | None = None,
    query_hint: str | None = None,
    offset: int = 0,
    exclude: set[str] | None = None,
) -> list[SourceChunk]:
    usage = usage or ChunkUsage()
    exclude = exclude or set()

    query = f"{chapter_title}: important concepts, definitions, facts and processes for {TYPE_LABELS[qtype].lower()}"
    if query_hint:
        query = f"{query_hint}. {query}"
    qvec = llm.embed([query], task="query")[0]

    similar = db.fetch_all(
        "select id::text, page, content, similarity from match_chunks(%s::vector, %s, %s::uuid[], %s)",
        (db.to_vector(qvec), textbook_id, [chapter_id], k * 2),
    )
    everything = db.fetch_all(
        "select id::text, page, content from chunks where chapter_id = %s order by page, id",
        (chapter_id,),
    )

    sim_score = {r["id"]: r["similarity"] for r in similar}
    candidates: dict[str, dict] = {r["id"]: r for r in similar}
    for r in _evenly_spaced(everything, k, offset):
        candidates.setdefault(r["id"], {**r, "similarity": sim_score.get(r["id"], 0.0)})
    if len(candidates) < k:  # small chapter: take whatever exists
        for r in everything:
            candidates.setdefault(r["id"], {**r, "similarity": 0.0})

    pool = [c for c in candidates.values() if c["id"] not in exclude] or list(candidates.values())
    # least-used first, then most similar
    pool.sort(key=lambda c: (usage.counts[c["id"]], -float(c.get("similarity") or 0.0)))
    chosen = pool[:k]
    chosen.sort(key=lambda c: c["page"])  # read in book order
    return [SourceChunk(id=c["id"], page=c["page"], content=c["content"]) for c in chosen]
