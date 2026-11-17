"""The contract every AI engine must follow."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Sequence


class LLMError(RuntimeError):
    pass


@dataclass
class SourceChunk:
    id: str
    page: int
    content: str


@dataclass
class QuestionRequest:
    """Everything the AI needs to write `count` questions of one type."""

    qtype: str
    count: int
    marks: float
    difficulties: list[str]
    chapter_title: str
    chunks: list[SourceChunk]
    class_level: str | None = None
    subject: str | None = None
    board: str | None = None
    avoid: list[str] = field(default_factory=list)
    extra_instructions: str | None = None
    feedback: str | None = None  # validation errors from the previous attempt


class LLMProvider(ABC):
    dim: int

    @abstractmethod
    def embed(self, texts: Sequence[str], task: Literal["document", "query"], titles: Sequence[str] | None = None) -> list[list[float]]:
        """Turn texts into unit-length vectors of size `dim`."""

    @abstractmethod
    def generate_questions(self, req: QuestionRequest) -> dict:
        """Return {"questions": [...]} matching LLMQuestionBatch (not yet validated)."""

    @abstractmethod
    def detect_chapters(self, outline: str, page_count: int) -> list[dict]:
        """Return [{"number", "title", "start_page"}] or [] if unsure."""


def normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
