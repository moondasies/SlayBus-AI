"""End-to-end API journey with two teachers, using the fake AI + local storage."""

import io

import pymupdf
import pytest
from docx import Document

from tests.conftest import login

FIFTY_MARKS = [
    {"name": "Section A", "type": "mcq", "count": 10, "marks_each": 1},
    {"name": "Section B", "type": "fill_blank", "count": 5, "marks_each": 1},
    {"name": "Section C", "type": "true_false", "count": 5, "marks_each": 1},
    {"name": "Section D", "type": "short_answer", "count": 5, "marks_each": 2},
    {"name": "Section E", "type": "long_answer", "count": 3, "marks_each": 5},
    {"name": "Section F", "type": "case_based", "count": 1, "marks_each": 5},
]


@pytest.fixture
def teacher(client):
    return login(client, "asha@school.in")


@pytest.fixture
def other(client):
    return login(client, "ravi@school.in")


@pytest.fixture
def book(client, teacher, sample_pdf):
    r = client.post("/textbooks", headers=teacher, data={"title": "Science Explorer", "subject": "Science",
                    "class_level": "7", "board": "CBSE"},
                    files={"file": ("book.pdf", sample_pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    # TestClient runs background tasks before returning, so ingestion is done.
    detail = client.get(f"/textbooks/{r.json()['id']}", headers=teacher).json()
    assert detail["status"] == "ready", detail
    return detail


def generate(client, headers, book, sections=FIFTY_MARKS, **extra):
    body = {"textbook_id": book["id"], "chapter_ids": [c["id"] for c in book["chapters"]], "sections": sections,
            "duration_min": 90, "difficulty": {"easy": 30, "medium": 50, "hard": 20}, **extra}
    r = client.post("/papers/generate", headers=headers, json=body)
    assert r.status_code == 202, r.text
    return client.get(f"/papers/{r.json()['id']}", headers=headers).json()


def test_health(client):
    body = client.get("/health", params={"check_db": True}).json()
    assert body["status"] == "ok" and body["database"]["ok"] and body["llm_provider"] == "fake"
    assert "test-secret" not in str(body)


def test_auth_required(client):
    assert client.get("/textbooks").status_code == 401
    assert client.get("/textbooks", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_profile_onboarding(client, teacher):
    me = client.get("/me", headers=teacher).json()
    assert me["onboarded"] is False and me["email"] == "asha@school.in"
    me = client.put("/me", headers=teacher, json={"name": "Asha", "school": "DPS", "board": "CBSE",
                                                  "subjects": ["Science"], "classes": ["7", "8"]}).json()
    assert me["onboarded"] is True and me["classes"] == ["7", "8"]


def test_upload_validation(client, teacher):
    r = client.post("/textbooks", headers=teacher, data={"title": "x"}, files={"file": ("a.pdf", b"hello", "application/pdf")})
    assert r.status_code == 415


def test_scanned_pdf_fails_with_reason(client, teacher):
    doc = pymupdf.open()
    doc.new_page()
    r = client.post("/textbooks", headers=teacher, data={"title": "Scan"}, files={"file": ("s.pdf", doc.tobytes(), "application/pdf")})
    detail = client.get(f"/textbooks/{r.json()['id']}", headers=teacher).json()
    assert detail["status"] == "failed" and "scanned" in detail["error_message"]


def test_ingestion_result(book):
    assert [c["title"] for c in book["chapters"]] == ["Nutrition in Plants", "Heat", "Water: A Precious Resource"]
    assert all(c["chunk_count"] > 0 for c in book["chapters"])
    assert book["chapter_method"] == "bookmarks" and book["progress"] == 100


def test_full_fifty_mark_paper_journey(client, teacher, other, book):
    paper = generate(client, teacher, book, title="Unit Test 1")
    assert paper["status"] == "ready", paper.get("error_message")
    qs = paper["questions"]
    assert len(qs) == 29 and paper["total_marks"] == 50

    # structure: sections in order, every question traceable to a page
    assert [q["section"] for q in qs] == sorted([q["section"] for q in qs])
    assert all(q["source_pages"] for q in qs), "every question must link to a textbook page"
    assert {q["chapter_title"] for q in qs} == {c["title"] for c in book["chapters"]}
    mcqs = [q for q in qs if q["type"] == "mcq"]
    assert all(len(q["options"]) == 4 and q["answer"] in q["options"] for q in mcqs)
    assert {q["difficulty"] for q in qs} == {"easy", "medium", "hard"}
    assert len({q["question_text"] for q in qs}) == len(qs), "no duplicates"

    # show source
    src = client.get(f"/questions/{qs[0]['id']}/sources", headers=teacher).json()
    assert src and src[0]["page"] in qs[0]["source_pages"]

    # edit text + marks
    q0 = qs[0]
    r = client.patch(f"/questions/{q0['id']}", headers=teacher, json={"question_text": "Edited question?", "marks": 2})
    assert r.status_code == 200 and r.json()["question_text"] == "Edited question?"
    assert client.get(f"/papers/{paper['id']}", headers=teacher).json()["total_marks"] == 51

    # invalid MCQ edit is refused
    r = client.patch(f"/questions/{mcqs[1]['id']}", headers=teacher, json={"answer": "not an option"})
    assert r.status_code == 422

    # regenerate keeps type/marks/section but changes the text
    target = [q for q in qs if q["type"] == "short_answer"][0]
    r = client.post(f"/questions/{target['id']}/regenerate", headers=teacher, json={"difficulty": "hard"})
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["question_text"] != target["question_text"]
    assert (new["type"], new["marks"], new["section"], new["difficulty"]) == ("short_answer", 2, target["section"], "hard")

    # delete from paper keeps it in the bank
    gone = qs[-1]
    assert client.delete(f"/questions/{gone['id']}", headers=teacher).status_code == 204
    paper2 = client.get(f"/papers/{paper['id']}", headers=teacher).json()
    assert len(paper2["questions"]) == 28 and paper2["total_marks"] == 46
    assert client.get(f"/questions/{gone['id']}", headers=teacher).json()["paper_id"] is None

    # add it back from the bank
    r = client.post(f"/papers/{paper['id']}/questions", headers=teacher, json={"question_id": gone["id"], "section": "Section F"})
    assert r.status_code == 201
    paper3 = client.get(f"/papers/{paper['id']}", headers=teacher).json()
    assert len(paper3["questions"]) == 29

    # reorder: reverse Section A
    ids = [q["id"] for q in paper3["questions"]]
    sec_a = [q["id"] for q in paper3["questions"] if q["section"] == "Section A"]
    new_order = list(reversed(sec_a)) + [i for i in ids if i not in sec_a]
    r = client.post(f"/papers/{paper['id']}/reorder", headers=teacher, json={"question_ids": new_order})
    assert [q["id"] for q in r.json()["questions"]][: len(sec_a)] == list(reversed(sec_a))
    assert client.post(f"/papers/{paper['id']}/reorder", headers=teacher, json={"question_ids": new_order[:3]}).status_code == 422

    # export PDF with and without answers
    pdf = client.get(f"/papers/{paper['id']}/export", headers=teacher, params={"format": "pdf", "answers": True})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    text = "".join(p.get_text() for p in pymupdf.open(stream=pdf.content, filetype="pdf"))
    assert "Unit Test 1" in text and "Answer Key" in text and "Edited question?" in text and "Maximum Marks: 51" in text
    no_ans = client.get(f"/papers/{paper['id']}/export", headers=teacher, params={"answers": False})
    assert "Answer Key" not in "".join(p.get_text() for p in pymupdf.open(stream=no_ans.content, filetype="pdf"))

    docx = client.get(f"/papers/{paper['id']}/export", headers=teacher, params={"format": "docx"})
    assert docx.status_code == 200
    words = "\n".join(p.text for p in Document(io.BytesIO(docx.content)).paragraphs)
    assert "Edited question?" in words and "Answer Key" in words

    # question bank filters
    bank = client.get("/questions", headers=teacher, params={"type": "mcq"}).json()
    assert bank["total"] == 10 and all(i["type"] == "mcq" for i in bank["items"])
    assert client.get("/questions", headers=teacher, params={"q": "Edited"}).json()["total"] == 1

    # privacy: the other teacher sees nothing of Asha's
    assert client.get("/textbooks", headers=other).json() == []
    assert client.get("/papers", headers=other).json() == []
    assert client.get("/questions", headers=other).json()["total"] == 0
    for url in (f"/textbooks/{book['id']}", f"/papers/{paper['id']}", f"/questions/{q0['id']}",
                f"/questions/{q0['id']}/sources", f"/papers/{paper['id']}/export"):
        assert client.get(url, headers=other).status_code == 404, url
    assert client.patch(f"/questions/{q0['id']}", headers=other, json={"marks": 9}).status_code == 404
    assert client.delete(f"/papers/{paper['id']}", headers=other).status_code == 404
    r = client.post("/papers/generate", headers=other, json={
        "textbook_id": book["id"], "chapter_ids": [book["chapters"][0]["id"]],
        "sections": [{"name": "A", "type": "mcq", "count": 1, "marks_each": 1}]})
    assert r.status_code == 404

    # deleting the paper keeps questions in the bank
    assert client.delete(f"/papers/{paper['id']}", headers=teacher).status_code == 204
    assert client.get("/questions", headers=teacher).json()["total"] >= 29


def test_worksheet_and_blueprint_errors(client, teacher, book):
    ws = generate(client, teacher, book, sections=[{"name": "Part 1", "type": "short_answer", "count": 2, "marks_each": 3}],
                  paper_type="worksheet")
    assert ws["status"] == "ready" and ws["paper_type"] == "worksheet"
    pdf = client.get(f"/papers/{ws['id']}/export", headers=teacher).content
    assert "Roll No" in "".join(p.get_text() for p in pymupdf.open(stream=pdf, filetype="pdf"))

    bad = {"textbook_id": book["id"], "chapter_ids": [book["chapters"][0]["id"]], "total_marks": 50,
           "sections": [{"name": "A", "type": "mcq", "count": 10, "marks_each": 1}]}
    r = client.post("/papers/generate", headers=teacher, json=bad)
    assert r.status_code == 422 and "add up to 10" in r.text


def test_delete_textbook(client, teacher, book):
    assert client.delete(f"/textbooks/{book['id']}", headers=teacher).status_code == 204
    assert client.get(f"/textbooks/{book['id']}", headers=teacher).status_code == 404
