"""SLAYBUS agent: FastAPI service for ingestion, RAG and paper generation."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db
from app.config import get_settings
from app.db import DatabaseNotConfigured, ping_database
from app.routers import papers, profile, questions, textbooks

VERSION = "0.2.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("slaybus")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Background jobs live inside this process. If it restarted mid-job, mark
    # those rows failed so the teacher sees "retry" instead of a stuck spinner.
    try:
        db.execute("update textbooks set status = 'failed', error_message = 'Processing was interrupted. Please retry.'"
                   " where status = 'processing' or status = 'uploaded'")
        db.execute("update papers set status = 'failed', error_message = 'Generation was interrupted. Please try again.'"
                   " where status = 'generating'")
    except Exception as e:  # DB not configured yet: /health will explain
        log.warning("Startup cleanup skipped: %s", e)
    yield


settings = get_settings()
if settings.dev_auth:
    log.warning("DEV_AUTH is ON: anyone can log in via /dev/token. Never enable this in production.")

app = FastAPI(
    title="SLAYBUS Agent",
    description="Classroom-ready papers. Powered by your syllabus.",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(DatabaseNotConfigured)
async def _db_not_configured(_: Request, exc: DatabaseNotConfigured):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(profile.router)
app.include_router(textbooks.router)
app.include_router(papers.router)
app.include_router(questions.router)


@app.get("/health", tags=["system"])
def health(check_db: bool = False) -> dict:
    """Is the agent alive? Add ?check_db=true to also test the database connection."""
    s = get_settings()
    result: dict = {
        "status": "ok",
        "service": "slaybus-agent",
        "version": VERSION,
        "llm_provider": s.llm_provider,
        "storage_backend": s.storage_backend,
        "models": {"generation": s.gemini_model, "embedding": s.gemini_embed_model},
        "missing_env": s.missing(),
        "dev_auth": s.dev_auth,
    }
    if check_db:
        ok, detail = ping_database()
        result["database"] = {"ok": ok, "detail": detail}
        if not ok:
            result["status"] = "degraded"
    return result
