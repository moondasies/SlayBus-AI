"""Real AI engine: Google Gemini (generation + embeddings)."""

from __future__ import annotations

import json
import logging
import time
from typing import Callable, Literal, Sequence, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from app.generate.prompts import (
    CHAPTER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_chapter_prompt,
    build_question_prompt,
)
from app.generate.schemas import LLMChapterList, LLMQuestionBatch
from app.llm.base import LLMError, LLMProvider, QuestionRequest, normalize

log = logging.getLogger("slaybus.gemini")
T = TypeVar("T")

EMBED_BATCH = 100  # Gemini accepts up to 100 texts per embed call
RETRYABLE = {408, 429, 500, 502, 503, 504}


def _with_retries(fn: Callable[[], T], what: str, attempts: int = 6) -> T:
    """Retry rate limits (429) and server hiccups with exponential backoff (2s -> 60s)."""
    delay = 2.0
    for i in range(attempts):
        try:
            return fn()
        except genai_errors.APIError as e:
            if e.code not in RETRYABLE or i == attempts - 1:
                raise LLMError(f"Gemini {what} failed ({e.code}): {e.message}") from e
            log.warning("Gemini %s got %s, retrying in %.0fs", what, e.code, delay)
        except Exception as e:  # network hiccups
            if i == attempts - 1:
                raise LLMError(f"Gemini {what} failed: {e}") from e
            log.warning("Gemini %s error %s, retrying in %.0fs", what, e, delay)
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise LLMError(f"Gemini {what} failed")  # pragma: no cover


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, embed_model: str, dim: int):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set (or use LLM_PROVIDER=fake for offline testing)")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.embed_model = embed_model
        self.dim = dim

    # ----------------------------------------------------------- embeddings
    def embed(self, texts: Sequence[str], task: Literal["document", "query"], titles: Sequence[str] | None = None) -> list[list[float]]:
        task_type = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"
        out: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = list(texts[start : start + EMBED_BATCH])
            config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dim)
            resp = _with_retries(
                lambda: self.client.models.embed_content(model=self.embed_model, contents=batch, config=config),
                "embedding",
            )
            if not resp.embeddings or len(resp.embeddings) != len(batch):
                raise LLMError("Gemini returned the wrong number of embeddings")
            # Gemini only pre-normalises the full 3072-dim vectors, so normalise smaller ones.
            out.extend(normalize(e.values or []) for e in resp.embeddings)
        return out

    # ----------------------------------------------------------- JSON calls
    def _json_call(self, system: str, prompt: str, schema: type[BaseModel], what: str, thinking_budget: int) -> dict:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.6,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        )
        resp = _with_retries(
            lambda: self.client.models.generate_content(model=self.model, contents=prompt, config=config),
            what,
        )
        text = resp.text or ""
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"Gemini returned invalid JSON for {what}: {text[:200]}") from e

    def generate_questions(self, req: QuestionRequest) -> dict:
        return self._json_call(SYSTEM_PROMPT, build_question_prompt(req), LLMQuestionBatch, "question generation", 1024)

    def detect_chapters(self, outline: str, page_count: int) -> list[dict]:
        data = self._json_call(
            CHAPTER_SYSTEM_PROMPT, build_chapter_prompt(outline, page_count), LLMChapterList, "chapter detection", 0
        )
        return list(data.get("chapters") or [])
