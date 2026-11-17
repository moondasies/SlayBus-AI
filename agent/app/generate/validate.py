"""Check every AI-written question before we trust it.

Structured output means we ask the AI for a fixed JSON shape instead of free
text. It's like giving the AI a form to fill in rather than a blank page. We
still check each filled-in form, because the AI can make mistakes:
wrong number of MCQ options, an answer that isn't one of the options, a
fill-in-the-blank with no blank, and so on.
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from app.generate.schemas import DIFFICULTIES, LLMQuestion

BLANK = re.compile(r"_{3,}")
LABEL = re.compile(r"^\s*(?:\(?[a-dA-D1-4][\).:]|option\s+[a-dA-D1-4][\).:]?)\s+", re.I)
LETTER_ANSWER = re.compile(r"^\s*(?:option\s*)?\(?([a-dA-D])\)?\.?\s*$", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def is_duplicate(text: str, existing: list[str], threshold: float = 0.8) -> bool:
    a = _tokens(text)
    if not a:
        return False
    for other in existing:
        b = _tokens(other)
        if b and len(a & b) / len(a | b) >= threshold:
            return True
    return False


def validate_question(raw: dict, qtype: str, marks: float, n_chunks: int) -> tuple[dict | None, str | None]:
    """Return (clean_question, None) or (None, reason)."""
    try:
        q = LLMQuestion.model_validate(raw)
    except ValidationError as e:
        return None, f"wrong JSON shape: {e.errors()[0]['msg']}"

    text = _norm(q.question_text) if qtype != "case_based" else q.question_text.strip()
    answer = _norm(q.answer)
    if len(text) < 10:
        return None, "question_text is empty or too short"
    if not answer:
        return None, f"missing answer for: {text[:60]}"

    difficulty = q.difficulty.strip().lower()
    if difficulty not in DIFFICULTIES:
        difficulty = "medium"

    options: list[str] | None = None
    points = [_norm(p) for p in q.marking_points if _norm(p)]

    if qtype == "mcq":
        options = [_norm(LABEL.sub("", o)) for o in q.options if _norm(o)]
        if len(options) != 4:
            return None, f"MCQ must have exactly 4 options, got {len(options)}: {text[:60]}"
        if len({o.lower() for o in options}) != 4:
            return None, f"MCQ options must be distinct: {text[:60]}"
        letter = LETTER_ANSWER.match(answer)
        if letter:
            answer = options["abcd".index(letter.group(1).lower())]
        else:
            match = [o for o in options if o.lower() == _norm(LABEL.sub("", answer)).lower()]
            if not match:
                return None, f"MCQ answer '{answer[:40]}' is not one of the options: {text[:60]}"
            answer = match[0]
        points = []
    elif qtype == "fill_blank":
        if not BLANK.search(text):
            return None, f"fill-in-the-blank has no '______' blank: {text[:60]}"
        text = BLANK.sub("______", text)
        points = []
    elif qtype == "true_false":
        a = answer.lower().rstrip(".")
        if a not in ("true", "false"):
            return None, f"true/false answer must be True or False, got '{answer[:20]}'"
        answer = a.capitalize()
        points = []
    elif qtype in ("long_answer", "case_based"):
        if len(points) < 2:
            return None, f"{qtype} needs at least 2 marking points: {text[:60]}"
    elif qtype == "short_answer" and not points:
        points = [answer]

    refs = sorted({r for r in q.source_refs if 1 <= r <= n_chunks})
    return {
        "question_text": text,
        "options": options,
        "answer": answer,
        "explanation": _norm(q.explanation) or None,
        "marking_points": points or None,
        "difficulty": difficulty,
        "source_refs": refs,
        "marks": marks,
    }, None
