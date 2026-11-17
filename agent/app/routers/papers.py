from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status

from app import db
from app.auth import CurrentUser, get_current_user
from app.export.docx import render_docx
from app.export.layout import PAPER_TYPE_LABELS, build_layout
from app.export.pdf import render_pdf
from app.generate.paper import generate_paper
from app.generate.schemas import AddFromBankRequest, Blueprint, PaperPatch, ReorderRequest
from app.routers.common import load_question, own_paper, own_question, own_textbook, paper_questions, recompute_total

router = APIRouter(prefix="/papers", tags=["papers"])


def _paper_out(paper: dict) -> dict:
    questions = paper_questions(paper)
    config = paper.get("config") or {}
    return {
        **paper,
        "total_marks": float(sum(q["marks"] for q in questions)) if questions else float(paper.get("total_marks") or 0),
        "sections": config.get("sections", []),
        "questions": questions,
    }


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
def create_paper(bp: Blueprint, background: BackgroundTasks, user: CurrentUser = Depends(get_current_user)):
    """Start generating a paper. Poll GET /papers/{id} until status is 'ready' or 'failed'."""
    book = own_textbook(str(bp.textbook_id), user.id)
    if book["status"] != "ready":
        raise HTTPException(409, f"This book is not ready yet (status: {book['status']})")
    found = db.fetch_all(
        "select id, title from chapters where textbook_id = %s and id = any(%s::uuid[]) order by number",
        (book["id"], [str(c) for c in bp.chapter_ids]),
    )
    if len(found) != len(bp.chapter_ids):
        raise HTTPException(422, "Some selected chapters don't belong to this book")

    config = bp.model_dump(mode="json")
    config["subject"] = bp.subject or book.get("subject")
    config["class_level"] = bp.class_level or book.get("class_level")
    config["board"] = bp.board or book.get("board")
    title = (bp.title or "").strip() or (
        f"{config['subject'] or book['title']}: {PAPER_TYPE_LABELS[bp.paper_type]}"
        + (f" ({found[0]['title']})" if len(found) == 1 else f" ({len(found)} chapters)")
    )
    paper = db.fetch_one(
        "insert into papers (user_id, textbook_id, title, paper_type, config, total_marks, duration_min, status)"
        " values (%s, %s, %s, %s, %s, %s, %s, 'generating') returning *",
        (user.id, book["id"], title[:200], bp.paper_type, db.jsonb(config), bp.computed_total, bp.duration_min),
    )
    background.add_task(generate_paper, str(paper["id"]))
    return {**paper, "sections": config["sections"], "questions": []}


@router.get("")
def list_papers(user: CurrentUser = Depends(get_current_user)):
    return db.fetch_all(
        "select p.id, p.title, p.paper_type, p.status, p.error_message, p.total_marks::float as total_marks,"
        " p.duration_min, p.created_at, p.textbook_id, t.title as textbook_title,"
        " (select count(*) from questions q where q.paper_id = p.id) as question_count"
        " from papers p left join textbooks t on t.id = p.textbook_id"
        " where p.user_id = %s order by p.created_at desc",
        (user.id,),
    )


@router.get("/{paper_id}")
def get_paper(paper_id: UUID, user: CurrentUser = Depends(get_current_user)):
    return _paper_out(own_paper(str(paper_id), user.id))


@router.patch("/{paper_id}")
def update_paper(paper_id: UUID, patch: PaperPatch, user: CurrentUser = Depends(get_current_user)):
    paper = own_paper(str(paper_id), user.id)
    changes = patch.model_dump(exclude_unset=True)
    config = dict(paper["config"] or {})
    if "instructions" in changes:
        config["instructions"] = changes.pop("instructions")
    title = changes.get("title", paper["title"])
    duration = changes.get("duration_min", paper["duration_min"])
    row = db.fetch_one(
        "update papers set title = %s, duration_min = %s, config = %s where id = %s returning *",
        (title, duration, db.jsonb(config), paper["id"]),
    )
    return _paper_out(row)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(paper_id: UUID, user: CurrentUser = Depends(get_current_user)):
    """Delete the paper. Its questions stay in the question bank."""
    paper = own_paper(str(paper_id), user.id)
    db.execute("delete from papers where id = %s", (paper["id"],))


@router.post("/{paper_id}/reorder")
def reorder_questions(paper_id: UUID, body: ReorderRequest, user: CurrentUser = Depends(get_current_user)):
    """Send every question id of the paper in the new order."""
    paper = own_paper(str(paper_id), user.id)
    ids = [str(i) for i in body.question_ids]
    current = {str(r["id"]) for r in db.fetch_all("select id from questions where paper_id = %s", (paper["id"],))}
    if set(ids) != current or len(ids) != len(current):
        raise HTTPException(422, "question_ids must list every question in this paper exactly once")
    with db.transaction() as conn:
        for i, qid in enumerate(ids, start=1):
            conn.execute("update questions set order_index = %s where id = %s", (i, qid))
    return _paper_out(paper)


@router.post("/{paper_id}/questions", status_code=status.HTTP_201_CREATED)
def add_from_bank(paper_id: UUID, body: AddFromBankRequest, user: CurrentUser = Depends(get_current_user)):
    """Copy a question from the question bank into this paper."""
    paper = own_paper(str(paper_id), user.id)
    src = own_question(str(body.question_id), user.id)
    row = db.fetch_one(
        "insert into questions (paper_id, user_id, chapter_id, section, order_index, type, difficulty, marks,"
        " question_text, options, answer, explanation, marking_points, source_chunk_ids)"
        " select %s, user_id, chapter_id, %s,"
        " (select coalesce(max(order_index), 0) + 1 from questions where paper_id = %s),"
        " type, difficulty, marks, question_text, options, answer, explanation, marking_points, source_chunk_ids"
        " from questions where id = %s returning id",
        (paper["id"], body.section, paper["id"], src["id"]),
    )
    recompute_total(paper["id"])
    return load_question(row["id"])


@router.get("/{paper_id}/export")
def export_paper(
    paper_id: UUID,
    format: str = Query("pdf", pattern="^(pdf|docx)$"),
    answers: bool = Query(True, description="Include the answer key / marking scheme"),
    user: CurrentUser = Depends(get_current_user),
):
    paper = own_paper(str(paper_id), user.id)
    if paper["status"] != "ready":
        raise HTTPException(409, "The paper isn't ready yet")
    questions = paper_questions(paper)
    if not questions:
        raise HTTPException(409, "This paper has no questions")
    layout = build_layout(paper, questions)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", paper["title"]).strip("-")[:60] or "paper"
    suffix = "-with-answers" if answers else ""
    if format == "pdf":
        content, media = render_pdf(layout, answers), "application/pdf"
    else:
        content = render_docx(layout, answers)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(
        content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{slug}{suffix}.{format}"'},
    )
