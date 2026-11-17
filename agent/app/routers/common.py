"""Shared helpers for routes: ownership checks and row loading.

Every lookup includes `user_id = <caller>`. If a teacher asks for someone
else's id they get 404 (not 403), so ids can't even be probed.
"""

from __future__ import annotations

from fastapi import HTTPException

from app import db

QUESTION_SELECT = """
select q.id, q.paper_id, q.chapter_id, ch.title as chapter_title, ch.number as chapter_number,
       q.section, q.order_index, q.type, q.difficulty, q.marks::float as marks, q.question_text,
       q.options, q.answer, q.explanation, q.marking_points, q.source_chunk_ids,
       coalesce((select array_agg(distinct c.page order by c.page) from chunks c
                 where c.id = any(q.source_chunk_ids)), '{}') as source_pages,
       q.created_at, q.updated_at
from questions q
left join chapters ch on ch.id = q.chapter_id
"""


def not_found(what: str) -> HTTPException:
    return HTTPException(404, f"{what} not found")


def own_textbook(textbook_id: str, user_id: str) -> dict:
    row = db.fetch_one("select * from textbooks where id = %s and user_id = %s", (textbook_id, user_id))
    if not row:
        raise not_found("Textbook")
    return row


def own_paper(paper_id: str, user_id: str) -> dict:
    row = db.fetch_one("select * from papers where id = %s and user_id = %s", (paper_id, user_id))
    if not row:
        raise not_found("Paper")
    return row


def own_question(question_id: str, user_id: str) -> dict:
    row = db.fetch_one("select * from questions where id = %s and user_id = %s", (question_id, user_id))
    if not row:
        raise not_found("Question")
    return row


def load_question(question_id: str) -> dict:
    return db.fetch_one(QUESTION_SELECT + " where q.id = %s", (question_id,))


def paper_questions(paper: dict) -> list[dict]:
    rows = db.fetch_all(QUESTION_SELECT + " where q.paper_id = %s order by q.order_index, q.created_at", (paper["id"],))
    order = {s["name"]: i for i, s in enumerate((paper.get("config") or {}).get("sections", []))}
    return sorted(rows, key=lambda q: (order.get(q["section"], len(order)), q["order_index"]))


def recompute_total(paper_id: str | None) -> None:
    if paper_id:
        db.execute(
            "update papers set total_marks = (select coalesce(sum(marks), 0) from questions where paper_id = %s) "
            "where id = %s",
            (paper_id, paper_id),
        )
