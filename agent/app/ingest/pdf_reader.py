"""Step 1 of ingestion: pull text out of the PDF, page by page."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import pymupdf


class PDFError(ValueError):
    pass


@dataclass
class Page:
    number: int  # 1-based PDF page number
    text: str


@dataclass
class PDFContent:
    pages: list[Page]
    toc: list[tuple[int, str, int]]  # (level, title, page) from PDF bookmarks

    @property
    def page_count(self) -> int:
        return len(self.pages)


_PAGE_NUM = re.compile(r"^\s*(page\s*)?\d{1,4}\s*$", re.I)


def _clean(text: str) -> str:
    text = text.replace("­", "")  # soft hyphens
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # join words split across lines
    text = re.sub(r"[ \t ]+", " ", text)
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if not _PAGE_NUM.match(ln)]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _strip_running_headers(pages: list[Page]) -> None:
    """Remove lines (e.g. book title, 'Reprint 2024-25') repeated on many pages."""
    if len(pages) < 6:
        return
    counts: Counter[str] = Counter()
    for p in pages:
        lines = [ln for ln in p.text.split("\n") if ln.strip()]
        edge = set(lines[:2] + lines[-2:])
        counts.update(edge)
    threshold = max(3, int(len(pages) * 0.3))
    repeated = {ln for ln, n in counts.items() if n >= threshold and len(ln) < 80}
    if not repeated:
        return
    for p in pages:
        p.text = "\n".join(ln for ln in p.text.split("\n") if ln not in repeated).strip()


def read_pdf(data: bytes) -> PDFContent:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        raise PDFError("This file could not be opened as a PDF") from e
    if doc.needs_pass:
        raise PDFError("This PDF is password-protected. Please upload an unlocked copy.")
    with doc:
        pages = [Page(number=i + 1, text=_clean(page.get_text("text"))) for i, page in enumerate(doc)]
        toc = [(lvl, title.strip(), page) for lvl, title, page, *_ in doc.get_toc(simple=True)]

    if not pages:
        raise PDFError("This PDF has no pages")
    _strip_running_headers(pages)
    total_chars = sum(len(p.text) for p in pages)
    if total_chars < 200 or total_chars / len(pages) < 40:
        raise PDFError(
            "This PDF has almost no selectable text. It is probably a scanned book; "
            "scanned PDFs (OCR) are not supported yet."
        )
    return PDFContent(pages=pages, toc=toc)
