"""Paper generation orchestrator.

Blueprint -> plan every question slot (section, chapter, difficulty)
-> for each (section, chapter) group: retrieve chunks -> ask the AI ->
validate -> retry/top-up -> save all questions with their source chunks.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app import db
from app.generate.schemas import Blueprint, DifficultyMix, SectionSpec
from app.generate.validate import is_duplicate, validate_question
from app.llm import get_llm
from app.llm.base import LLMError, LLMProvider, QuestionRequest, SourceChunk
from app.rag.retriever import ChunkUsage, retrieve_for_chapter

log = logging.getLogger("slaybus.generate")

MAX_ATTEMPTS = 3  # first try + up to 2 retries/top-ups per group
DIFF_RANK = {"easy": 0, "medium": 1, "hard": 2}


class GenerationError(RuntimeError):
    pass


# ------------------------------------------------------------------ planning
def allocate_difficulties(count: int, mix: DifficultyMix) -> list[str]:
    """Split `count` questions by percentage using largest-remainder rounding."""
    shares = {"easy": mix.easy, "medium": mix.medium, "hard": mix.hard}
    exact = {k: count * v / 100 for k, v in shares.items()}
    alloc = {k: int(v) for k, v in exact.items()}
    left = count - sum(alloc.values())
    for k in sorted(exact, key=lambda k: (exact[k] - alloc[k], shares[k]), reverse=True)[:left]:
        alloc[k] += 1
    return [d for d in ("easy", "medium", "hard") for _ in range(alloc[d])]


@dataclass
class Chapter:
    id: str
    number: int
    title: str


@dataclass
class Group:
    section: SectionSpec
    section_index: int
    chapter: Chapter
    difficulties: list[str] = field(default_factory=list)


def plan_groups(bp: Blueprint, chapters: list[Chapter]) -> list[Group]:
    groups: dict[tuple[int, str], Group] = {}
    for si, sec in enumerate(bp.sections):
        diffs = allocate_difficulties(sec.count, bp.difficulty)
        # interleave so every chapter gets a mix of difficulties
        order = sorted(range(sec.count), key=lambda i: (i % 2, i))
        for slot, i in enumerate(order):
            ch = chapters[(slot + si) % len(chapters)]
            g = groups.setdefault((si, ch.id), Group(sec, si, ch))
            g.difficulties.append(diffs[i])
    return list(groups.values())


# ---------------------------------------------------------------- generation
@dataclass
class Context:
    llm: LLMProvider
    textbook_id: str
    class_level: str | None
    subject: str | None
    board: str | None
    usage: ChunkUsage
    lock: threading.Lock
    accepted_texts: list[str]


def _ask(ctx: Context, qtype: str, count: int, marks: float, difficulties: list[str], chapter: Chapter,
         chunks: list[SourceChunk], extra: str | None, avoid: list[str]) -> tuple[list[dict], list[str]]:
    """Run up to MAX_ATTEMPTS AI calls until `count` valid, unique questions exist."""
    accepted: list[dict] = []
    problems: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        need = count - len(accepted)
        if need <= 0:
            break
        with ctx.lock:
            avoid_now = avoid + ctx.accepted_texts + [q["question_text"] for q in accepted]
        req = QuestionRequest(
            qtype=qtype, count=need, marks=marks, difficulties=difficulties[len(accepted):][:need] or ["medium"] * need,
            chapter_title=chapter.title, chunks=chunks, class_level=ctx.class_level, subject=ctx.subject,
            board=ctx.board, avoid=avoid_now, extra_instructions=extra,
            feedback="\n".join(f"- {p}" for p in problems[-8:]) or None,
        )
        try:
            raw = ctx.llm.generate_questions(req)
        except LLMError as e:
            problems.append(str(e))
            log.warning("AI call failed: %s", e)
            continue
        for item in (raw.get("questions") or [])[: need + 2]:
            clean, err = validate_question(item, qtype, marks, len(chunks))
            if err:
                problems.append(err)
                continue
            with ctx.lock:
                if is_duplicate(clean["question_text"], avoid_now + ctx.accepted_texts):
                    problems.append(f"duplicate question: {clean['question_text'][:60]}")
                    continue
                ctx.accepted_texts.append(clean["question_text"])
            refs = clean.pop("source_refs") or list(range(1, len(chunks) + 1))
            clean["source_chunk_ids"] = [chunks[r - 1].id for r in refs]
            clean["chapter_id"] = chapter.id
            accepted.append(clean)
            avoid_now.append(clean["question_text"])
            if len(accepted) >= count:
                break
    return accepted, problems


def _run_group(ctx: Context, g: Group) -> list[dict]:
    k = min(10, max(4, len(g.difficulties) * 2))
    with ctx.lock:
        chunks = retrieve_for_chapter(ctx.llm, ctx.textbook_id, g.chapter.id, g.chapter.title, g.section.type, k, ctx.usage,
                                      offset=g.section_index)
        ctx.usage.mark([c.id for c in chunks])
    if not chunks:
        log.warning("chapter %s has no chunks", g.chapter.title)
        return []
    questions, problems = _ask(ctx, g.section.type, len(g.difficulties), g.section.marks_each, g.difficulties,
                               g.chapter, chunks, g.section.instructions, [])
    if len(questions) < len(g.difficulties):
        log.warning("group %s/%s: %d/%d questions; problems: %s", g.section.name, g.chapter.title,
                    len(questions), len(g.difficulties), problems[-3:])
    for q in questions:
        q["section"] = g.section.name
        q["_section_index"] = g.section_index
        q["_chapter_number"] = g.chapter.number
    return questions


def load_chapters(textbook_id: str, chapter_ids: list[str]) -> list[Chapter]:
    rows = db.fetch_all(
        "select id::text, number, title from chapters where textbook_id = %s and id = any(%s::uuid[]) order by number",
        (textbook_id, chapter_ids),
    )
    return [Chapter(**r) for r in rows]


def generate_paper(paper_id: str) -> None:
    """Background job. Never raises: the outcome is written to the paper row."""
    paper = db.fetch_one("select * from papers where id = %s", (paper_id,))
    if not paper:
        return
    try:
        bp = Blueprint.model_validate(paper["config"])
        chapters = load_chapters(str(bp.textbook_id), [str(c) for c in bp.chapter_ids])
        if not chapters:
            raise GenerationError("None of the selected chapters exist anymore")
        ctx = Context(get_llm(), str(bp.textbook_id), bp.class_level, bp.subject, bp.board,
                      ChunkUsage(), threading.Lock(), [])
        groups = plan_groups(bp, chapters)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda g: _run_group(ctx, g), groups))
        questions = [q for qs in results for q in qs]
        if not questions:
            raise GenerationError("The AI could not produce any valid questions. Try other chapters or fewer questions.")

        questions.sort(key=lambda q: (q["_section_index"], DIFF_RANK[q["difficulty"]], q["_chapter_number"]))
        counters: dict[str, int] = defaultdict(int)
        with db.transaction() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "insert into questions (paper_id, user_id, chapter_id, section, order_index, type, difficulty, marks,"
                    " question_text, options, answer, explanation, marking_points, source_chunk_ids)"
                    " values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::uuid[])",
                    [
                        (paper_id, paper["user_id"], q["chapter_id"], q["section"], _next(counters, q["section"]),
                         bp.sections[q["_section_index"]].type, q["difficulty"], q["marks"], q["question_text"],
                         db.jsonb(q["options"]), q["answer"], q["explanation"], db.jsonb(q["marking_points"]),
                         q["source_chunk_ids"])
                        for q in questions
                    ],
                )
            wanted = sum(s.count for s in bp.sections)
            note = None if len(questions) == wanted else (
                f"Generated {len(questions)} of {wanted} questions; the selected chapters didn't have enough "
                "material for the rest. You can add more from the question bank or regenerate."
            )
            conn.execute(
                "update papers set status = 'ready', error_message = %s,"
                " total_marks = (select coalesce(sum(marks), 0) from questions where paper_id = %s) where id = %s",
                (note, paper_id, paper_id),
            )
    except Exception as e:
        log.exception("paper %s failed", paper_id)
        msg = str(e) if isinstance(e, (GenerationError, LLMError)) else f"Unexpected error: {type(e).__name__}"
        db.execute("update papers set status = 'failed', error_message = %s where id = %s", (msg, paper_id))


def _next(counters: dict[str, int], section: str) -> int:
    counters[section] += 1
    return counters[section]


# --------------------------------------------------------- single question
def regenerate_question(question: dict, paper: dict, difficulty: str | None, instructions: str | None) -> dict:
    """Write one fresh question to replace `question`. Returns the updated fields."""
    bp_conf = paper["config"] or {}
    if not question.get("chapter_id"):
        raise GenerationError("This question is not linked to a chapter, so it can't be regenerated")
    chapter = db.fetch_one("select id::text, number, title from chapters where id = %s", (question["chapter_id"],))
    if not chapter:
        raise GenerationError("The chapter for this question no longer exists")
    llm = get_llm()
    siblings = db.fetch_all("select question_text from questions where paper_id = %s", (paper["id"],))
    avoid = [r["question_text"] for r in siblings]

    # different chunks than last time, shifted window over the chapter
    seed = len(avoid) + int(str(question["id"]).replace("-", "")[:4], 16)
    chunks = retrieve_for_chapter(
        llm, str(paper["textbook_id"]), chapter["id"], chapter["title"], question["type"], 6,
        query_hint=instructions, offset=seed, exclude=set(map(str, question.get("source_chunk_ids") or [])),
    )
    if not chunks:
        raise GenerationError("No textbook text found for this chapter")
    ctx = Context(llm, str(paper["textbook_id"]), bp_conf.get("class_level"), bp_conf.get("subject"),
                  bp_conf.get("board"), ChunkUsage(), threading.Lock(), [])
    qs, problems = _ask(ctx, question["type"], 1, float(question["marks"]), [difficulty or question["difficulty"]],
                        Chapter(**chapter), chunks, instructions, avoid)
    if not qs:
        raise GenerationError("Couldn't generate a valid replacement. " + "; ".join(problems[-2:]))
    return qs[0]
