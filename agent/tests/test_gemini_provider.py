"""Exercise GeminiProvider against the real google-genai types, with the network mocked."""

from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.generate.schemas import LLMQuestionBatch
from app.llm import gemini as gemini_mod
from app.llm.base import LLMError, QuestionRequest, SourceChunk
from app.llm.gemini import GeminiProvider


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(gemini_mod.time, "sleep", lambda s: None)
    return GeminiProvider(api_key="test-key", model="gemini-2.5-flash", embed_model="gemini-embedding-001", dim=4)


def test_requires_key():
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiProvider(api_key="", model="m", embed_model="e", dim=4)


def test_generate_questions_sends_schema_and_parses_json(provider, monkeypatch):
    seen = {}

    def fake_generate(*, model, contents, config):
        seen.update(model=model, contents=contents, config=config)
        return SimpleNamespace(text='{"questions": [{"question_text": "Q?", "options": [], "answer": "A",'
                                     ' "explanation": "", "marking_points": [], "difficulty": "easy", "source_refs": [1]}]}')

    monkeypatch.setattr(provider.client.models, "generate_content", fake_generate)
    req = QuestionRequest(qtype="short_answer", count=1, marks=2, difficulties=["easy"], chapter_title="Heat",
                          chunks=[SourceChunk(id="c1", page=5, content="Heat flows from hot to cold.")],
                          class_level="7", subject="Science", board="CBSE", avoid=["Old question?"])
    out = provider.generate_questions(req)
    assert out["questions"][0]["answer"] == "A"
    cfg: types.GenerateContentConfig = seen["config"]
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_schema is LLMQuestionBatch
    assert "Heat flows from hot to cold." in seen["contents"] and "Old question?" in seen["contents"]
    assert 'page="5"' in seen["contents"] and "Class 7" in seen["contents"]


def test_invalid_json_raises(provider, monkeypatch):
    monkeypatch.setattr(provider.client.models, "generate_content", lambda **kw: SimpleNamespace(text="not json"))
    with pytest.raises(LLMError, match="invalid JSON"):
        provider.detect_chapters("outline", 10)


def test_embed_batches_normalises_and_retries(provider, monkeypatch):
    calls = []

    def fake_embed(*, model, contents, config):
        calls.append((len(contents), config.task_type, config.output_dimensionality))
        if len(calls) == 1:
            raise genai_errors.APIError(429, {"error": {"message": "slow down", "status": "RESOURCE_EXHAUSTED"}})
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0, 0.0, 0.0]) for _ in contents])

    monkeypatch.setattr(provider.client.models, "embed_content", fake_embed)
    vecs = provider.embed([f"t{i}" for i in range(150)], task="document")
    assert len(vecs) == 150 and vecs[0] == [0.6, 0.8, 0.0, 0.0]
    assert calls == [(100, "RETRIEVAL_DOCUMENT", 4), (100, "RETRIEVAL_DOCUMENT", 4), (50, "RETRIEVAL_DOCUMENT", 4)]


def test_non_retryable_error_surfaces(provider, monkeypatch):
    def boom(**kw):
        raise genai_errors.APIError(400, {"error": {"message": "bad request", "status": "INVALID_ARGUMENT"}})

    monkeypatch.setattr(provider.client.models, "embed_content", boom)
    with pytest.raises(LLMError, match="400"):
        provider.embed(["x"], task="query")
