"""SLAYBUS agent: FastAPI service for ingestion, RAG and paper generation."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import ping_database

VERSION = "0.1.0"

settings = get_settings()

app = FastAPI(
    title="SLAYBUS Agent",
    description="Classroom-ready papers. Powered by your syllabus.",
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health(check_db: bool = False) -> dict:
    """Is the agent alive? Add ?check_db=true to also test the Supabase connection."""
    s = get_settings()
    result: dict = {
        "status": "ok",
        "service": "slaybus-agent",
        "version": VERSION,
        "models": {"generation": s.gemini_model, "embedding": s.gemini_embed_model},
        "missing_env": s.missing(),
    }
    if check_db:
        ok, detail = ping_database()
        result["database"] = {"ok": ok, "detail": detail}
        if not ok:
            result["status"] = "degraded"
    return result
