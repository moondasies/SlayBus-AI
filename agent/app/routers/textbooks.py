from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from app import db, storage
from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.ingest.pipeline import ingest_textbook
from app.routers.common import own_textbook

router = APIRouter(prefix="/textbooks", tags=["textbooks"])

LIST_SQL = """
select t.id, t.title, t.subject, t.class_level, t.board, t.status, t.progress, t.error_message, t.page_count,
       t.chapter_method, t.created_at,
       (select count(*) from chapters c where c.textbook_id = t.id) as chapter_count
from textbooks t
"""


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_textbook(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="Textbook PDF"),
    title: str = Form(..., min_length=1, max_length=200),
    subject: str | None = Form(None, max_length=80),
    class_level: str | None = Form(None, max_length=40),
    board: str | None = Form(None, max_length=80),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload a PDF, store it, and start ingestion in the background."""
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"PDF is larger than {get_settings().max_upload_mb} MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "Please upload a PDF file")

    book_id = str(uuid.uuid4())
    path = f"{user.id}/{book_id}.pdf"
    try:
        storage.upload(path, data)
    except storage.StorageError as e:
        raise HTTPException(502, str(e)) from e

    row = db.fetch_one(
        "insert into textbooks (id, user_id, title, subject, class_level, board, file_path, status, progress) "
        "values (%s, %s, %s, %s, %s, %s, %s, 'uploaded', 0) returning id",
        (book_id, user.id, title.strip(), _clean(subject), _clean(class_level), _clean(board), path),
    )
    background.add_task(ingest_textbook, book_id)
    return db.fetch_one(LIST_SQL + " where t.id = %s", (row["id"],))


@router.get("")
def list_textbooks(user: CurrentUser = Depends(get_current_user)):
    return db.fetch_all(LIST_SQL + " where t.user_id = %s order by t.created_at desc", (user.id,))


@router.get("/{textbook_id}")
def get_textbook(textbook_id: UUID, user: CurrentUser = Depends(get_current_user)):
    own_textbook(str(textbook_id), user.id)
    book = db.fetch_one(LIST_SQL + " where t.id = %s", (str(textbook_id),))
    book["chapters"] = db.fetch_all(
        "select c.id, c.number, c.title, c.start_page, c.end_page,"
        " (select count(*) from chunks k where k.chapter_id = c.id) as chunk_count"
        " from chapters c where c.textbook_id = %s order by c.number",
        (str(textbook_id),),
    )
    return book


@router.post("/{textbook_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_textbook(textbook_id: UUID, background: BackgroundTasks, user: CurrentUser = Depends(get_current_user)):
    """Run ingestion again (e.g. after a failure)."""
    book = own_textbook(str(textbook_id), user.id)
    if book["status"] == "processing":
        raise HTTPException(409, "This book is already being processed")
    db.execute("update textbooks set status = 'uploaded', progress = 0, error_message = null where id = %s", (book["id"],))
    background.add_task(ingest_textbook, str(book["id"]))
    return {"id": book["id"], "status": "uploaded"}


@router.delete("/{textbook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_textbook(textbook_id: UUID, user: CurrentUser = Depends(get_current_user)):
    """Delete the book, its chapters and chunks. Papers and questions are kept."""
    book = own_textbook(str(textbook_id), user.id)
    db.execute("delete from textbooks where id = %s and user_id = %s", (book["id"], user.id))
    try:
        storage.delete(book["file_path"])
    except storage.StorageError:
        pass  # the row is gone; a leftover file is harmless
