"""Offline stand-in for Gemini, used by tests and keyless demos (LLM_PROVIDER=fake).

It is NOT smart. It builds simple questions by copying sentences out of the
retrieved excerpts, so the whole pipeline (retrieve -> generate -> validate ->
save -> edit -> export) can be exercised without an API key or internet.

Embeddings are a "hashed bag of words": each word bumps one of `dim` slots,
so texts that share words end up close together, which is enough for
vector search to behave sensibly in tests.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal, Sequence

from app.llm.base import LLMProvider, QuestionRequest, normalize

WORD = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")
STOP = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "had", "her", "was", "one", "our",
    "out", "has", "have", "this", "that", "with", "from", "they", "their", "there", "which", "these", "those",
    "into", "also", "such", "when", "what", "where", "will", "would", "about", "other", "than", "then", "them",
    "some", "more", "most", "very", "each", "been", "being", "does", "were", "your", "only", "called", "known",
}


def _words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text)]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
    return [p.strip() for p in parts if 40 <= len(p.strip()) <= 260 and p.strip()[0].isupper()]


def _keyword(sentence: str) -> str | None:
    cands = [w for w in WORD.findall(sentence) if len(w) >= 5 and w.lower() not in STOP]
    return max(cands, key=len) if cands else None


class FakeProvider(LLMProvider):
    def __init__(self, dim: int = 768):
        self.dim = dim

    def embed(self, texts: Sequence[str], task: Literal["document", "query"], titles: Sequence[str] | None = None) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * self.dim
            for w in _words(t):
                if w in STOP:
                    continue
                h = int(hashlib.md5(w.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            if not any(vec):
                vec[0] = 1.0
            out.append(normalize(vec))
        return out

    def detect_chapters(self, outline: str, page_count: int) -> list[dict]:
        return []

    def generate_questions(self, req: QuestionRequest) -> dict:
        from app.generate.validate import is_duplicate

        avoid = list(req.avoid)
        pool: list[tuple[int, str]] = []
        for i, c in enumerate(req.chunks, start=1):
            pool += [(i, s) for s in _sentences(c.content)]
        vocab = sorted({w for _, s in pool for w in WORD.findall(s) if len(w) >= 5 and w.lower() not in STOP})

        questions = []
        for idx, (ref, sent) in enumerate(pool):
            if len(questions) >= req.count:
                break
            kw = _keyword(sent)
            if not kw:
                continue
            diff = req.difficulties[min(len(questions), len(req.difficulties) - 1)] if req.difficulties else "medium"
            q = self._make(req, sent, kw, vocab, idx, pool)
            if q is None or is_duplicate(q["question_text"], avoid):
                continue
            avoid.append(q["question_text"])
            q.update(difficulty=diff, source_refs=[ref])
            questions.append(q)
        return {"questions": questions}

    def _make(self, req: QuestionRequest, sent: str, kw: str, vocab: list[str], idx: int, pool: list) -> dict | None:
        blanked = re.sub(rf"\b{re.escape(kw)}\b", "______", sent, count=1)
        distractors = [w for w in vocab if w.lower() != kw.lower()]
        # rotate so different questions get different distractors
        distractors = distractors[idx % max(1, len(distractors)) :] + distractors[: idx % max(1, len(distractors))]
        base = {"options": [], "marking_points": [], "explanation": f"Stated in the textbook: \"{sent}\""}
        marks = max(1, int(round(req.marks)))

        if req.qtype == "mcq":
            opts = [kw] + distractors[:3]
            if len({o.lower() for o in opts}) < 4:
                return None
            # put the correct answer in a different slot each time
            opts = opts[1:][: idx % 4] + [kw] + opts[1:][idx % 4 :]
            return {**base, "question_text": f"Choose the word that best completes: \"{blanked}\"", "options": opts, "answer": kw}
        if req.qtype == "fill_blank":
            return {**base, "question_text": blanked, "answer": kw}
        if req.qtype == "true_false":
            if idx % 2 == 0 or not distractors:
                return {**base, "question_text": sent, "answer": "True"}
            return {**base, "question_text": re.sub(rf"\b{re.escape(kw)}\b", distractors[0], sent, count=1), "answer": "False"}
        if req.qtype in ("short_answer", "long_answer"):
            nxt = [s for _, s in pool[idx + 1 : idx + marks + 1]]
            points = ([sent] + nxt)[: max(2, marks)]
            if len(points) < 2:
                points = [sent, f"Mentions the term '{kw}' correctly."]
            verb = "Explain" if req.qtype == "long_answer" else "Briefly describe"
            return {**base, "question_text": f"{verb} in your own words: \"{sent}\"", "answer": " ".join(points), "marking_points": points}
        if req.qtype == "case_based":
            passage = " ".join(s for _, s in pool[idx : idx + 3])
            subs = [f"(i) What does the passage say about '{kw.lower()}'? [{marks - 1 if marks > 1 else 1}]"]
            if marks > 1:
                subs.append("(ii) State one fact from the passage in your own words. [1]")
            return {
                **base,
                "question_text": f"Read the passage and answer the questions.\n\n{passage}\n\n" + "\n".join(subs),
                "answer": sent,
                "marking_points": [sent, "Any one correct fact from the passage."],
            }
        return None
