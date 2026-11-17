"""Step 2 of ingestion: find where each chapter starts and ends.

Three strategies, best first:
1. PDF bookmarks (the clickable table of contents many PDFs carry)
2. Heading patterns at the top of pages, like "Chapter 3" or "Lesson 4: Light"
3. Ask the AI to read the contents page + first line of every page
If all fail, the whole book becomes one chapter so the teacher can still use it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.ingest.pdf_reader import PDFContent
from app.llm.base import LLMProvider

log = logging.getLogger("slaybus.chapters")

SKIP_TITLES = re.compile(
    r"^(contents?|table of contents|preface|foreword|acknowledg|about the|index|glossary|appendix|answers?|"
    r"bibliography|references|copyright|title page|cover|notes?|textbook development|a note for|rationalised)",
    re.I,
)
CHAPTER_WORD = re.compile(r"\b(chapter|lesson|unit)\b", re.I)
HEADING = re.compile(
    r"^(?:chapter|lesson|unit|ch\.)\s*[-–:.]?\s*(\d{1,3}|[IVXLC]{1,7})\b\s*[-–:.]?\s*(.*)$",
    re.I,
)
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


@dataclass
class ChapterSpan:
    number: int
    title: str
    start_page: int
    end_page: int


def _roman_to_int(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = ROMAN.get(ch, 0)
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def _finish(starts: list[tuple[str, int]], page_count: int) -> list[ChapterSpan]:
    """Turn (title, start_page) pairs into numbered spans with end pages."""
    starts = sorted({p: t for t, p in starts}.items())  # one chapter per start page
    spans = []
    for i, (start, title) in enumerate(starts):
        end = starts[i + 1][0] - 1 if i + 1 < len(starts) else page_count
        spans.append(ChapterSpan(number=i + 1, title=title[:200], start_page=start, end_page=max(start, end)))
    return spans


PREFIX = re.compile(r"^(?:chapter|lesson|unit|ch\.)\s*(?:\d{1,3}|[IVXLC]{1,7})\b\s*[:.\-–]?\s*", re.I)


def _clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip(" .:-–")
    t = PREFIX.sub("", t) or t
    return t or "Untitled chapter"


def from_toc(pdf: PDFContent) -> list[ChapterSpan]:
    toc = [(lvl, t, p) for lvl, t, p in pdf.toc if 1 <= p <= pdf.page_count and t]
    if not toc:
        return []
    levels = sorted({lvl for lvl, _, _ in toc})[:3]
    # Prefer the level that literally says "Chapter ..."; otherwise the top level.
    best = max(levels, key=lambda L: sum(1 for lvl, t, _ in toc if lvl == L and CHAPTER_WORD.search(t)))
    if not any(lvl == best and CHAPTER_WORD.search(t) for lvl, t, _ in toc):
        best = levels[0]
    entries = [(_clean_title(t), p) for lvl, t, p in toc if lvl == best and not SKIP_TITLES.match(t.strip())]
    if len(entries) < 2:
        return []
    return _finish(entries, pdf.page_count)


def from_headings(pdf: PDFContent) -> list[ChapterSpan]:
    found: dict[int, tuple[str, int]] = {}
    for page in pdf.pages:
        lines = [ln.strip() for ln in page.text.split("\n") if ln.strip()]
        top = lines[:6]
        matches = [(i, HEADING.match(ln)) for i, ln in enumerate(top)]
        matches = [(i, m) for i, m in matches if m]
        all_matches = sum(1 for ln in lines if HEADING.match(ln))
        if not matches or all_matches >= 3:  # 3+ "Chapter N" lines = a contents page, skip
            continue
        i, m = matches[0]
        raw = m.group(1)
        num = int(raw) if raw.isdigit() else _roman_to_int(raw)
        title = m.group(2).strip()
        if not title and i + 1 < len(top):
            title = top[i + 1]
        if num and num not in found:
            found[num] = (_clean_title(title or f"Chapter {num}"), page.number)

    if len(found) < 2:
        return []
    # Keep only chapters whose start pages increase with their number.
    ordered, last_page = [], 0
    for num in sorted(found):
        title, page = found[num]
        if page > last_page:
            ordered.append((f"{title}", page))
            last_page = page
    return _finish(ordered, pdf.page_count) if len(ordered) >= 2 else []


def build_outline(pdf: PDFContent, full_pages: int = 6, max_chars: int = 30000) -> str:
    parts = []
    for p in pdf.pages[:full_pages]:
        parts.append(f"=== PDF page {p.number} (full text) ===\n{p.text[:3000]}")
    parts.append("=== First lines of every page ===")
    for p in pdf.pages:
        first = " | ".join([ln for ln in p.text.split("\n") if ln.strip()][:2])[:120]
        parts.append(f"page {p.number}: {first}")
    return "\n".join(parts)[:max_chars]


def from_llm(pdf: PDFContent, llm: LLMProvider) -> list[ChapterSpan]:
    try:
        raw = llm.detect_chapters(build_outline(pdf), pdf.page_count)
    except Exception as e:  # chapter detection is best-effort
        log.warning("LLM chapter detection failed: %s", e)
        return []
    entries = []
    for ch in raw:
        try:
            start = int(ch["start_page"])
            title = _clean_title(str(ch.get("title") or ""))
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= start <= pdf.page_count and not SKIP_TITLES.match(title):
            entries.append((title, start))
    return _finish(entries, pdf.page_count) if len(entries) >= 2 else []


def strip_heading(text: str, title: str) -> str:
    """Remove the 'Chapter 3 / Light' heading lines from a chapter's first page,
    so they don't leak into the first sentence of the chunk text."""
    lines = text.split("\n")
    norm_title = re.sub(r"\W+", " ", title).strip().lower()
    for _ in range(3):
        if not lines:
            break
        first = lines[0].strip()
        norm = re.sub(r"\W+", " ", first).strip().lower()
        if not first or HEADING.match(first) or (norm and norm == norm_title):
            lines.pop(0)
        else:
            break
    return "\n".join(lines)


def detect_chapters(pdf: PDFContent, llm: LLMProvider) -> tuple[list[ChapterSpan], str]:
    for method, fn in (("bookmarks", lambda: from_toc(pdf)), ("headings", lambda: from_headings(pdf)), ("ai", lambda: from_llm(pdf, llm))):
        spans = fn()
        if spans:
            return spans, method
    return [ChapterSpan(number=1, title="Full textbook", start_page=1, end_page=pdf.page_count)], "whole_book"
