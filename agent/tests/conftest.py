"""Test setup.

Unit tests run anywhere. API tests need a local Postgres with pgvector:
    export TEST_DATABASE_URL=postgresql://postgres@localhost:5432/slaybus_test
They use the offline fake AI and local file storage, so no keys are needed.
"""

import os
import sys
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(AGENT_DIR / "scripts"))

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")


def _reset_caches():
    from app.config import get_settings
    from app.db import get_pool
    from app.llm import get_llm

    if get_pool.cache_info().currsize:
        get_pool().close()
    for fn in (get_settings, get_pool, get_llm):
        fn.cache_clear()


@pytest.fixture(autouse=True)
def test_env(monkeypatch, tmp_path_factory):
    monkeypatch.setenv("DATABASE_URL", TEST_DB)
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path_factory.getbasetemp() / "storage"))
    monkeypatch.setenv("DEV_AUTH", "true")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-that-is-long-enough-for-hs256")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _reset_caches()
    yield
    _reset_caches()


@pytest.fixture(scope="session")
def database():
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL not set")
    from setup_local_db import setup

    setup(TEST_DB, reset=True)
    return TEST_DB


@pytest.fixture
def client(database):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory) -> bytes:
    from make_sample_textbook import build

    path = tmp_path_factory.mktemp("pdf") / "book.pdf"
    build(str(path))
    return path.read_bytes()


def login(client, email: str) -> dict:
    r = client.post("/dev/token", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
