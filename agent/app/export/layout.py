"""Shared paper layout used by both PDF and DOCX export."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.generate.schemas import TYPE_LABELS

PAPER_TYPE_LABELS = {"question_paper": "Question Paper", "worksheet": "Worksheet", "quiz": "Quiz"}
DEFAULT_INSTRUCTIONS = [
    "All questions are compulsory.",
    "Marks for each question are shown in brackets.",
    "Write neat, well-labelled answers.",
]


@dataclass
class QItem:
    number: int
    type: str
    text: str
    marks: float
    options: list[str] | None
    answer: str | None
    explanation: str | None
    marking_points: list[str] | None
    pages: list[int]


@dataclass
class SectionItem:
    name: str
    heading: str
    instructions: str | None
    questions: list[QItem] = field(default_factory=list)

    @property
    def marks(self) -> float:
        return sum(q.marks for q in self.questions)


@dataclass
class PaperLayout:
    title: str
    paper_type: str
    meta_left: list[str]
    meta_right: list[str]
    instructions: list[str]
    sections: list[SectionItem]
    show_student_fields: bool

    @property
    def total_marks(self) -> float:
        return sum(s.marks for s in self.sections)


def fmt_marks(m: float) -> str:
    return f"{m:g}"


def build_layout(paper: dict, questions: list[dict]) -> PaperLayout:
    config = paper.get("config") or {}
    section_specs = {s["name"]: s for s in config.get("sections", [])}
    order = [s["name"] for s in config.get("sections", [])]
    for q in questions:
        if q["section"] not in order:
            order.append(q["section"])

    sections: list[SectionItem] = []
    n = 0
    for name in order:
        qs = [q for q in questions if q["section"] == name]
        if not qs:
            continue
        spec = section_specs.get(name, {})
        qtype = spec.get("type") or qs[0]["type"]
        marks = {float(q["marks"]) for q in qs}
        each = f"{len(qs)} × {fmt_marks(marks.pop())} = {fmt_marks(sum(float(q['marks']) for q in qs))} marks" if len(marks) == 1 \
            else f"{fmt_marks(sum(float(q['marks']) for q in qs))} marks"
        sec = SectionItem(name=name, heading=f"{name}: {TYPE_LABELS.get(qtype, qtype)} ({each})",
                          instructions=spec.get("instructions"))
        for q in qs:
            n += 1
            sec.questions.append(QItem(
                number=n, type=q["type"], text=q["question_text"], marks=float(q["marks"]),
                options=q.get("options"), answer=q.get("answer"), explanation=q.get("explanation"),
                marking_points=q.get("marking_points"), pages=q.get("source_pages") or [],
            ))
        sections.append(sec)

    total = sum(s.marks for s in sections)
    left = [x for x in [
        f"Class: {config['class_level']}" if config.get("class_level") else None,
        f"Subject: {config['subject']}" if config.get("subject") else None,
        f"Board: {config['board']}" if config.get("board") else None,
    ] if x]
    right = [x for x in [
        f"Time: {paper['duration_min']} minutes" if paper.get("duration_min") else None,
        f"Maximum Marks: {fmt_marks(total)}",
    ] if x]
    custom = (config.get("instructions") or "").strip()
    instructions = [ln.strip(" -•") for ln in custom.splitlines() if ln.strip()] if custom else list(DEFAULT_INSTRUCTIONS)
    return PaperLayout(
        title=paper["title"], paper_type=paper.get("paper_type") or "question_paper", meta_left=left, meta_right=right,
        instructions=instructions, sections=sections, show_student_fields=paper.get("paper_type") in ("worksheet", "quiz"),
    )


def answer_lines(q: QItem, paper_type: str) -> int:
    """Blank writing lines to leave under a question on worksheets."""
    if paper_type != "worksheet":
        return 0
    return {"short_answer": 3, "long_answer": 7, "case_based": 5}.get(q.type, 0)
