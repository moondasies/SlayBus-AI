from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "slaybus-agent"
    assert isinstance(body["missing_env"], list)
    assert "database" not in body


def test_health_reports_db_failure(monkeypatch):
    monkeypatch.setattr("app.main.ping_database", lambda: (False, "boom"))
    body = client.get("/health", params={"check_db": True}).json()
    assert body["status"] == "degraded"
    assert body["database"] == {"ok": False, "detail": "boom"}


def test_health_reports_db_success(monkeypatch):
    monkeypatch.setattr("app.main.ping_database", lambda: (True, "connected"))
    body = client.get("/health", params={"check_db": True}).json()
    assert body["status"] == "ok"
    assert body["database"]["ok"] is True


def test_health_never_leaks_secrets(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    db.get_settings.cache_clear()
    try:
        assert "super-secret-value" not in client.get("/health").text
    finally:
        db.get_settings.cache_clear()
