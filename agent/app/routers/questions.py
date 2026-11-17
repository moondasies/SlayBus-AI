from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import db
from app.auth import CurrentUser, get_current_user
from app.generate.paper import GenerationError, regenerate_question
from app.generate.schemas import Difficulty, QuestionPatch, QuestionType, RegenerateRequest
from app.generate.validate import validate_question
from app.llm.base import LLMError
from app.routers.common import QUESTION_SELECT, load_question, own_paper, own_question, recompute_total

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("")
def question_bank(
    user: CurrentUser = Depends(get_current_user),
    textbook_id: UUID | None = None,
    chapter_id: UUID | None = None,
    type: QuestionType | None = None,
    difficulty: Difficulty | None = None,
    q: str | None = Query(None, max_length=100, description="Search text"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Every question this teacher has generated, with filters."""
    where, params = ["q.user_id = %s"], [user.id]
    if textbook_id:
        where.append("ch.textbook_id = %s")
        params.append(str(textbook_id))
    if chapter_id:
        where.append("q.chapter_id = %s")
        params.append(str(chapter_id))
    if type:
        where.append("q.type = %s")
        params.append(type)
    if difficulty:
        where.append("q.difficulty = %s")
        params.append(difficulty)
    if q:
        where.append("q.question_text ilike %s")
        params.append(f"%{q.replace('%', '').replace('_', ' ')}%")
    sql = QUESTION_SELECT + " where " + " and ".join(where)
    total = db.fetch_one(f"select count(*) as n from ({sql}) s", params)["n"]
    rows = db.fetch_all(sql + " order by q.created_at desc limit %s offset %s", params + [limit, offset])
    return {"total": total, "items": rows}


@router.get("/{question_id}")
def get_question(question_id: UUID, user: CurrentUser = Depends(get_current_user)):
    own_question(str(question_id), user.id)
    return load_question(str(question_id))


@router.get("/{question_id}/sources")
def question_sources(question_id: UUID, user: CurrentUser = Depends(get_current_user)):
    """The textbook passages this question was written from ("show source page")."""
    qrow = own_question(str(question_id), user.id)
    return db.fetch_all(
        "select c.id, c.page, c.content, ch.title as chapter_title from chunks c"
        " left join chapters ch on ch.id = c.chapter_id"
        " join textbooks t on t.id = c.textbook_id and t.user_id = %s"
        " where c.id = any(%s::uuid[]) order by c.page",
        (user.id, [str(x) for x in qrow["source_chunk_ids"] or []]),
    )


@router.patch("/{question_id}")
def edit_question(question_id: UUID, patch: QuestionPatch, user: CurrentUser = Depends(get_current_user)):
    current = own_question(str(question_id), user.id)
    changes = patch.model_dump(exclude_unset=True)
    if not changes:
        return load_question(str(question_id))

    # keep MCQs consistent: 4 options and the answer must be one of them
    if current["type"] == "mcq" and ({"options", "answer"} & changes.keys()):
        merged = {
            "question_text": changes.get("question_text", current["question_text"]),
            "options": changes.get("options", current["options"] or []),
            "answer": changes.get("answer", current["answer"] or ""),
            "explanation": changes.get("explanation", current["explanation"] or ""),
            "marking_points": [], "difficulty": current["difficulty"], "source_refs": [],
        }
        clean, err = validate_question(merged, "mcq", float(current["marks"]), 0)
        if err:
            raise HTTPException(422, err)
        changes["options"], changes["answer"] = clean["options"], clean["answer"]

    for key in ("options", "marking_points"):
        if key in changes:
            changes[key] = db.jsonb(changes[key])
    cols = ", ".join(f"{k} = %({k})s" for k in changes)
    db.execute(f"update questions set {cols} where id = %(id)s", {**changes, "id": str(question_id)})
    if "marks" in changes:
        recompute_total(current["paper_id"])
    return load_question(str(question_id))


@router.post("/{question_id}/regenerate")
def regenerate(question_id: UUID, body: RegenerateRequest | None = None, user: CurrentUser = Depends(get_current_user)):
    """Replace this question with a fresh one from the same chapter (same type and marks)."""
    body = body or RegenerateRequest()
    question = own_question(str(question_id), user.id)
    if not question["paper_id"]:
        raise HTTPException(409, "Only questions inside a paper can be regenerated")
    paper = own_paper(str(question["paper_id"]), user.id)
    if not paper["textbook_id"]:
        raise HTTPException(409, "The textbook for this paper was deleted")
    try:
        new = regenerate_question(question, paper, body.difficulty, body.instructions)
    except (GenerationError, LLMError) as e:
        raise HTTPException(502, str(e)) from e
    db.execute(
        "update questions set question_text = %s, options = %s, answer = %s, explanation = %s, marking_points = %s,"
        " difficulty = %s, source_chunk_ids = %s::uuid[] where id = %s",
        (new["question_text"], db.jsonb(new["options"]), new["answer"], new["explanation"],
         db.jsonb(new["marking_points"]), new["difficulty"], new["source_chunk_ids"], str(question_id)),
    )
    return load_question(str(question_id))


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: UUID,
    keep_in_bank: bool = Query(True, description="true = only remove from its paper; false = delete forever"),
    user: CurrentUser = Depends(get_current_user),
):
    question = own_question(str(question_id), user.id)
    if keep_in_bank and question["paper_id"]:
        db.execute("update questions set paper_id = null where id = %s", (question["id"],))
    else:
        db.execute("delete from questions where id = %s", (question["id"],))
    recompute_total(question["paper_id"])
