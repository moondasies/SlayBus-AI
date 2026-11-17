"""Ingestion orchestrator: PDF in storage -> chapters + embedded chunks in Postgres."""

from __future__ import annotations

import logging

from app import db, storage
from app.config import get_settings
from app.ingest.chapters import detect_chapters, strip_heading
from app.ingest.chunker import chunk_pages
from app.ingest.embedder import embed_texts
from app.ingest.pdf_reader import Page, PDFError, read_pdf
from app.llm import get_llm
from app.llm.base import LLMError

log = logging.getLogger("slaybus.ingest")


def _set(textbook_id: str, **fields) -> None:
    cols = ", ".join(f"{k} = %({k})s" for k in fields)
    db.execute(f"update textbooks set {cols} where id = %(id)s", {**fields, "id": textbook_id})


def ingest_textbook(textbook_id: str) -> None:
    """Runs in the background after upload. Never raises: failures are saved on the row."""
    s = get_settings()
    book = db.fetch_one("select id, file_path from textbooks where id = %s", (textbook_id,))
    if not book:
        return
    try:
        _set(textbook_id, status="processing", progress=5, error_message=None)
        llm = get_llm()

        pdf = read_pdf(storage.download(book["file_path"]))
        _set(textbook_id, page_count=pdf.page_count, progress=15)

        spans, method = detect_chapters(pdf, llm)
        log.info("textbook %s: %d chapters via %s", textbook_id, len(spans), method)
        _set(textbook_id, progress=25, chapter_method=method)

        chapter_chunks = []
        for span in spans:
            pages = [
                Page(p.number, strip_heading(p.text, span.title) if p.number == span.start_page else p.text)
                for p in pdf.pages if span.start_page <= p.number <= span.end_page
            ]
            chapter_chunks.append((span, chunk_pages(pages, s.chunk_tokens, s.chunk_overlap_tokens)))
        all_chunks = [(span, c) for span, cs in chapter_chunks for c in cs]
        if not all_chunks:
            raise PDFError("No text could be extracted from the chapters")

        def progress(done: int, total: int) -> None:
            _set(textbook_id, progress=25 + int(70 * done / total))

        vectors = embed_texts(
            llm,
            [f"{span.title}\n\n{c.content}" for span, c in all_chunks],
            titles=[span.title for span, _ in all_chunks],
            on_progress=progress,
        )

        with db.transaction() as conn:
            conn.execute("delete from chunks where textbook_id = %s", (textbook_id,))
            conn.execute("delete from chapters where textbook_id = %s", (textbook_id,))
            chapter_ids = {}
            for span in spans:
                row = conn.execute(
                    "insert into chapters (textbook_id, number, title, start_page, end_page) "
                    "values (%s, %s, %s, %s, %s) returning id",
                    (textbook_id, span.number, span.title, span.start_page, span.end_page),
                ).fetchone()
                chapter_ids[span.number] = row["id"]
            with conn.cursor() as cur:
                cur.executemany(
                    "insert into chunks (textbook_id, chapter_id, page, content, token_count, embedding) "
                    "values (%s, %s, %s, %s, %s, %s::vector)",
                    [
                        (textbook_id, chapter_ids[span.number], c.page, c.content, c.token_count, db.to_vector(v))
                        for (span, c), v in zip(all_chunks, vectors)
                    ],
                )
            conn.execute(
                "update textbooks set status = 'ready', progress = 100, error_message = null where id = %s",
                (textbook_id,),
            )
        log.info("textbook %s ready: %d chunks", textbook_id, len(all_chunks))
    except (PDFError, LLMError) as e:
        log.warning("textbook %s failed: %s", textbook_id, e)
        _set(textbook_id, status="failed", error_message=str(e))
    except Exception as e:  # unexpected: keep the row honest, log the trace
        log.exception("textbook %s crashed", textbook_id)
        _set(textbook_id, status="failed", error_message=f"Unexpected error while processing: {type(e).__name__}")
