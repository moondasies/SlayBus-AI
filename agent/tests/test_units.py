import time

import jwt
import pytest

from app.generate.paper import allocate_difficulties
from app.generate.schemas import Blueprint, DifficultyMix
from app.generate.validate import is_duplicate, validate_question
from app.ingest.chunker import chunk_pages
from app.ingest.pdf_reader import Page, PDFError, read_pdf


def q(**kw):
    base = {"question_text": "What do plants make during photosynthesis?", "options": [], "answer": "Glucose",
            "explanation": "", "marking_points": [], "difficulty": "easy", "source_refs": [1]}
    return {**base, **kw}


# ------------------------------------------------------------ difficulty mix
@pytest.mark.parametrize("count,mix,expected", [
    (10, (30, 50, 20), {"easy": 3, "medium": 5, "hard": 2}),
    (3, (30, 50, 20), {"easy": 1, "medium": 1, "hard": 1}),
    (1, (0, 0, 100), {"easy": 0, "medium": 0, "hard": 1}),
    (7, (34, 33, 33), {"easy": 3, "medium": 2, "hard": 2}),
])
def test_allocate_difficulties(count, mix, expected):
    out = allocate_difficulties(count, DifficultyMix(easy=mix[0], medium=mix[1], hard=mix[2]))
    assert len(out) == count
    assert {d: out.count(d) for d in ("easy", "medium", "hard")} == expected


def test_difficulty_must_sum_to_100():
    with pytest.raises(ValueError):
        DifficultyMix(easy=50, medium=50, hard=10)


def test_blueprint_total_marks_must_match():
    base = {"textbook_id": "00000000-0000-0000-0000-000000000001",
            "chapter_ids": ["00000000-0000-0000-0000-000000000002"],
            "sections": [{"name": "A", "type": "mcq", "count": 10, "marks_each": 1}]}
    assert Blueprint(**base, total_marks=10).computed_total == 10
    with pytest.raises(ValueError, match="add up to 10"):
        Blueprint(**base, total_marks=50)


# ------------------------------------------------------------ validation
def test_mcq_valid_and_letter_answer_mapped():
    clean, err = validate_question(q(options=["A) Glucose", "B) Oxygen", "C) Water", "D) Soil"], answer="A"), "mcq", 1, 3)
    assert err is None
    assert clean["options"] == ["Glucose", "Oxygen", "Water", "Soil"]
    assert clean["answer"] == "Glucose"


@pytest.mark.parametrize("options,answer,msg", [
    (["Glucose", "Oxygen", "Water"], "Glucose", "exactly 4"),
    (["Glucose", "glucose", "Water", "Soil"], "Glucose", "distinct"),
    (["Glucose", "Oxygen", "Water", "Soil"], "Starch", "not one of the options"),
])
def test_mcq_invalid(options, answer, msg):
    clean, err = validate_question(q(options=options, answer=answer), "mcq", 1, 3)
    assert clean is None and msg in err


def test_fill_blank_needs_blank():
    assert validate_question(q(question_text="Plants make glucose by photosynthesis."), "fill_blank", 1, 1)[1]
    clean, err = validate_question(q(question_text="Plants make ___ by photosynthesis."), "fill_blank", 1, 1)
    assert err is None and "______" in clean["question_text"]


def test_true_false_normalised():
    clean, _ = validate_question(q(question_text="Leaves have stomata.", answer="true."), "true_false", 1, 1)
    assert clean["answer"] == "True"
    assert validate_question(q(answer="Maybe"), "true_false", 1, 1)[1]


def test_long_answer_needs_marking_points():
    assert validate_question(q(marking_points=["one"]), "long_answer", 5, 1)[1]
    clean, err = validate_question(q(marking_points=["one", "two"]), "long_answer", 5, 1)
    assert err is None and clean["marks"] == 5


def test_source_refs_out_of_range_dropped():
    clean, _ = validate_question(q(source_refs=[0, 2, 9]), "short_answer", 2, 3)
    assert clean["source_refs"] == [2]


def test_bad_shape_rejected():
    assert validate_question({"question_text": "x"}, "mcq", 1, 1)[1].startswith("wrong JSON shape")


def test_duplicates():
    assert is_duplicate("What is photosynthesis?", ["what is Photosynthesis"])
    assert not is_duplicate("What is a stoma?", ["Define conduction of heat."])


# ------------------------------------------------------------ chunking / pdf
def test_chunker_keeps_pages_and_overlaps():
    pages = [Page(n, " ".join(f"Sentence {n}-{i} talks about plants and light." for i in range(80))) for n in (1, 2, 3)]
    chunks = chunk_pages(pages, chunk_tokens=200, overlap_tokens=40)
    assert len(chunks) > 3
    assert all(c.token_count <= 220 for c in chunks)
    assert {c.page for c in chunks} == {1, 2, 3}
    # overlap: the start of each chunk appears at the end of the previous one
    assert chunks[1].content[:30] in chunks[0].content


def test_read_pdf_rejects_garbage():
    with pytest.raises(PDFError):
        read_pdf(b"not a pdf")


def test_read_pdf_rejects_textless_pdf():
    import pymupdf
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()
    with pytest.raises(PDFError, match="scanned"):
        read_pdf(doc.tobytes())


def test_sample_book_chapters(sample_pdf):
    from app.ingest.chapters import detect_chapters
    from app.llm.fake import FakeProvider

    spans, method = detect_chapters(read_pdf(sample_pdf), FakeProvider())
    assert method == "bookmarks"
    assert [s.title for s in spans] == ["Nutrition in Plants", "Heat", "Water: A Precious Resource"]


# ------------------------------------------------------------ auth
def test_token_checks():
    from fastapi import HTTPException

    from app.auth import decode_token, mint_dev_token

    good = mint_dev_token("11111111-1111-1111-1111-111111111111", "a@b.co")
    assert decode_token(good)["sub"] == "11111111-1111-1111-1111-111111111111"

    wrong_key = jwt.encode({"sub": "x", "aud": "authenticated", "exp": time.time() + 60}, "another-secret-of-decent-length-xx")
    expired = jwt.encode({"sub": "x", "aud": "authenticated", "exp": time.time() - 60}, "test-secret-that-is-long-enough-for-hs256")
    wrong_aud = jwt.encode({"sub": "x", "aud": "anon", "exp": time.time() + 60}, "test-secret-that-is-long-enough-for-hs256")
    for bad in (wrong_key, expired, wrong_aud, "garbage"):
        with pytest.raises(HTTPException) as e:
            decode_token(bad)
        assert e.value.status_code == 401


def test_strip_heading():
    from app.ingest.chapters import strip_heading

    assert strip_heading("Chapter 1\nNutrition in Plants\nAll living things need food.", "Nutrition in Plants") \
        == "All living things need food."
    assert strip_heading("All living things need food.", "Heat") == "All living things need food."
