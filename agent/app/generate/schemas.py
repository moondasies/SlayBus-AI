"""Pydantic models: the shapes of blueprints, AI output and API payloads."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

QuestionType = Literal["mcq", "fill_blank", "true_false", "short_answer", "long_answer", "case_based"]
Difficulty = Literal["easy", "medium", "hard"]
PaperType = Literal["question_paper", "worksheet", "quiz"]

QUESTION_TYPES: tuple[str, ...] = ("mcq", "fill_blank", "true_false", "short_answer", "long_answer", "case_based")
DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard")

TYPE_LABELS = {
    "mcq": "Multiple Choice Questions",
    "fill_blank": "Fill in the Blanks",
    "true_false": "True or False",
    "short_answer": "Short Answer Questions",
    "long_answer": "Long Answer Questions",
    "case_based": "Case-Based Questions",
}


# ---------------------------------------------------------------- blueprint
class SectionSpec(BaseModel):
    name: str = Field(min_length=1, max_length=60, examples=["Section A"])
    type: QuestionType
    count: int = Field(ge=1, le=50)
    marks_each: float = Field(gt=0, le=20)
    instructions: str | None = Field(default=None, max_length=300)


class DifficultyMix(BaseModel):
    easy: int = Field(default=30, ge=0, le=100)
    medium: int = Field(default=50, ge=0, le=100)
    hard: int = Field(default=20, ge=0, le=100)

    @model_validator(mode="after")
    def _sums_to_100(self) -> "DifficultyMix":
        if self.easy + self.medium + self.hard != 100:
            raise ValueError("Difficulty percentages must add up to 100")
        return self


class Blueprint(BaseModel):
    """What the teacher fills in on the 'Create paper' form."""

    textbook_id: UUID
    chapter_ids: list[UUID] = Field(min_length=1, max_length=30)
    title: str | None = Field(default=None, max_length=200)
    paper_type: PaperType = "question_paper"
    class_level: str | None = Field(default=None, max_length=40)
    subject: str | None = Field(default=None, max_length=80)
    board: str | None = Field(default=None, max_length=80)
    total_marks: float | None = Field(default=None, gt=0, le=500)
    duration_min: int | None = Field(default=None, ge=5, le=360)
    instructions: str | None = Field(default=None, max_length=1000)
    sections: list[SectionSpec] = Field(min_length=1, max_length=10)
    difficulty: DifficultyMix = Field(default_factory=DifficultyMix)

    @field_validator("chapter_ids")
    @classmethod
    def _unique_chapters(cls, v: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def _check_totals(self) -> "Blueprint":
        total_q = sum(s.count for s in self.sections)
        if total_q > 100:
            raise ValueError(f"Too many questions ({total_q}); the limit is 100 per paper")
        computed = sum(s.count * s.marks_each for s in self.sections)
        if self.total_marks is not None and abs(computed - self.total_marks) > 1e-6:
            raise ValueError(f"Sections add up to {computed:g} marks but total_marks is {self.total_marks:g}")
        names = [s.name.strip().lower() for s in self.sections]
        if len(set(names)) != len(names):
            raise ValueError("Section names must be unique")
        return self

    @property
    def computed_total(self) -> float:
        return sum(s.count * s.marks_each for s in self.sections)


# ---------------------------------------------------------------- AI output
# Every field is required (no defaults) so it can be sent to Gemini as a
# response schema. The model fills empty lists where a field doesn't apply.
class LLMQuestion(BaseModel):
    question_text: str
    options: list[str]
    answer: str
    explanation: str
    marking_points: list[str]
    difficulty: str
    source_refs: list[int]


class LLMQuestionBatch(BaseModel):
    questions: list[LLMQuestion]


class LLMChapter(BaseModel):
    number: int
    title: str
    start_page: int


class LLMChapterList(BaseModel):
    chapters: list[LLMChapter]


# ---------------------------------------------------------------- API inputs
class QuestionPatch(BaseModel):
    question_text: str | None = Field(default=None, min_length=1, max_length=5000)
    options: list[str] | None = Field(default=None, max_length=6)
    answer: str | None = Field(default=None, max_length=5000)
    explanation: str | None = Field(default=None, max_length=5000)
    marking_points: list[str] | None = Field(default=None, max_length=20)
    marks: float | None = Field(default=None, gt=0, le=50)
    difficulty: Difficulty | None = None
    section: str | None = Field(default=None, min_length=1, max_length=60)


class RegenerateRequest(BaseModel):
    difficulty: Difficulty | None = None
    instructions: str | None = Field(default=None, max_length=500, examples=["Make it about the water cycle"])


class ReorderRequest(BaseModel):
    question_ids: list[UUID] = Field(min_length=1)


class PaperPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    duration_min: int | None = Field(default=None, ge=5, le=360)
    instructions: str | None = Field(default=None, max_length=1000)


class AddFromBankRequest(BaseModel):
    question_id: UUID
    section: str = Field(min_length=1, max_length=60)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    school: str | None = Field(default=None, max_length=200)
    board: str | None = Field(default=None, max_length=80)
    subjects: list[str] | None = Field(default=None, max_length=20)
    classes: list[str] | None = Field(default=None, max_length=20)
