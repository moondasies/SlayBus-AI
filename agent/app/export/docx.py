"""Editable Word (DOCX) export, for teachers who want to tweak the paper in Word."""

from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Mm, Pt

from app.export.layout import PAPER_TYPE_LABELS, PaperLayout, QItem, answer_lines, fmt_marks


def _header(doc: Document, layout: PaperLayout, subtitle: str) -> None:
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run(layout.title)
    r.bold = True
    r.font.size = Pt(15)
    s = doc.add_paragraph(subtitle)
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rows = max(len(layout.meta_left), len(layout.meta_right))
    if rows:
        table = doc.add_table(rows=rows, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i in range(rows):
            table.cell(i, 0).text = layout.meta_left[i] if i < len(layout.meta_left) else ""
            cell = table.cell(i, 1)
            cell.text = layout.meta_right[i] if i < len(layout.meta_right) else ""
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph("_" * 90)


def _question(doc: Document, q: QItem, paper_type: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    p.add_run(f"{q.number}. ").bold = True
    p.add_run(q.text)
    p.add_run(f"   [{fmt_marks(q.marks)}]").bold = True
    if q.type == "mcq" and q.options:
        for i, o in enumerate(q.options[:4]):
            op = doc.add_paragraph(f"({'abcd'[i]}) {o}")
            op.paragraph_format.left_indent = Mm(8)
            op.paragraph_format.space_after = Pt(0)
    for _ in range(answer_lines(q, paper_type)):
        doc.add_paragraph("_" * 85)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _answer(doc: Document, q: QItem) -> None:
    if q.type == "mcq" and q.options and q.answer in q.options:
        ans = f"({'abcd'[q.options.index(q.answer)]}) {q.answer}"
    else:
        ans = q.answer or "—"
    p = doc.add_paragraph()
    p.add_run(f"{q.number}. ").bold = True
    p.add_run(ans)
    for pt in q.marking_points or []:
        b = doc.add_paragraph(pt, style="List Bullet")
        b.paragraph_format.left_indent = Mm(10)
    notes = []
    if q.explanation:
        notes.append(q.explanation)
    if q.pages:
        notes.append("Source: p. " + ", ".join(str(x) for x in q.pages))
    if notes:
        n = doc.add_paragraph()
        r = n.add_run(" · ".join(notes))
        r.italic = True
        r.font.size = Pt(8.5)


def render_docx(layout: PaperLayout, include_answers: bool) -> bytes:
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Mm(16))
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)

    _header(doc, layout, PAPER_TYPE_LABELS.get(layout.paper_type, "Question Paper"))
    if layout.show_student_fields:
        doc.add_paragraph("Name: ____________________   Class/Section: ________   Roll No.: ______")
    if layout.instructions:
        doc.add_paragraph().add_run("General Instructions:").bold = True
        for i, ins in enumerate(layout.instructions, 1):
            doc.add_paragraph(f"{i}. {ins}")

    for s in layout.sections:
        h = doc.add_paragraph()
        h.add_run(s.heading).bold = True
        if s.instructions:
            doc.add_paragraph(s.instructions).runs[0].italic = True
        for q in s.questions:
            _question(doc, q, layout.paper_type)

    if include_answers:
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        _header(doc, layout, "Answer Key & Marking Scheme")
        for s in layout.sections:
            doc.add_paragraph().add_run(s.heading).bold = True
            for q in s.questions:
                _answer(doc, q)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
