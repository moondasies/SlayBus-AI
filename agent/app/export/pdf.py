"""Printable PDF export (A4) with an optional answer key on new pages."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from app.export.layout import PaperLayout, QItem, answer_lines, fmt_marks

FONT_DIR = Path(__file__).parent / "fonts"
_registered = False


def _fonts() -> None:
    """DejaVu Serif covers Greek letters, maths symbols and ₹, unlike built-in PDF fonts."""
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont("Serif", str(FONT_DIR / "DejaVuSerif.ttf")))
    pdfmetrics.registerFont(TTFont("Serif-Bold", str(FONT_DIR / "DejaVuSerif-Bold.ttf")))
    pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-Bold", italic="Serif", boldItalic="Serif-Bold")
    _registered = True


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="Serif", fontSize=10.5, leading=14.5)
    return {
        "title": ParagraphStyle("title", parent=base, fontName="Serif-Bold", fontSize=15, leading=19, alignment=TA_CENTER),
        "sub": ParagraphStyle("sub", parent=base, fontSize=9.5, alignment=TA_CENTER, textColor=colors.HexColor("#444444")),
        "meta": base,
        "section": ParagraphStyle("section", parent=base, fontName="Serif-Bold", fontSize=11.5, spaceBefore=10, spaceAfter=4),
        "note": ParagraphStyle("note", parent=base, fontSize=9.5, textColor=colors.HexColor("#444444")),
        "q": base,
        "opt": ParagraphStyle("opt", parent=base, leftIndent=0),
        "ans": ParagraphStyle("ans", parent=base, leftIndent=0, textColor=colors.HexColor("#222222")),
        "small": ParagraphStyle("small", parent=base, fontSize=8.5, textColor=colors.HexColor("#666666")),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _question_block(q: QItem, st: dict, width: float, paper_type: str) -> list:
    num_w, marks_w = 9 * mm, 12 * mm
    row = [_p(f"{q.number}.", st["q"]), _p(q.text, st["q"]), _p(f"[{fmt_marks(q.marks)}]", st["q"])]
    table = Table([row], colWidths=[num_w, width - num_w - marks_w, marks_w])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("ALIGN", (2, 0), (2, 0), "RIGHT")]))
    parts: list = [table]
    if q.type == "mcq" and q.options:
        labels = "abcd"
        cells = [_p(f"({labels[i]}) {o}", st["opt"]) for i, o in enumerate(q.options[:4])]
        short = all(len(o) <= 32 for o in q.options)
        grid = [cells[:2], cells[2:4]] if short else [[c] for c in cells]
        col_w = (width - num_w) / (2 if short else 1)
        opt = Table(grid, colWidths=[col_w] * (2 if short else 1))
        opt.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        wrap = Table([["", opt]], colWidths=[num_w, width - num_w])
        wrap.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        parts.append(wrap)
    for _ in range(answer_lines(q, paper_type)):
        parts.append(Spacer(1, 5 * mm))
        parts.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#BBBBBB")))
    parts.append(Spacer(1, 3 * mm))
    return [KeepTogether(parts)]


def _answer_block(q: QItem, st: dict) -> list:
    out = []
    if q.type == "mcq" and q.options and q.answer in q.options:
        ans = f"({'abcd'[q.options.index(q.answer)]}) {q.answer}"
    else:
        ans = q.answer or "—"
    out.append(Paragraph(f"<b>{q.number}.</b> {escape(ans).replace(chr(10), '<br/>')}", st["ans"]))
    if q.marking_points:
        for pt in q.marking_points:
            out.append(Paragraph(f"&nbsp;&nbsp;&nbsp;• {escape(pt)}", st["ans"]))
    extra = []
    if q.explanation:
        extra.append(q.explanation)
    if q.pages:
        extra.append("Source: p. " + ", ".join(str(p) for p in q.pages))
    if extra:
        out.append(_p("    " + " · ".join(extra), st["small"]))
    out.append(Spacer(1, 2.5 * mm))
    return [KeepTogether(out)]


def _header(layout: PaperLayout, st: dict, width: float, subtitle: str) -> list:
    out = [_p(layout.title, st["title"]), _p(subtitle, st["sub"]), Spacer(1, 4 * mm)]
    rows = max(len(layout.meta_left), len(layout.meta_right))
    if rows:
        data = [[_p(layout.meta_left[i] if i < len(layout.meta_left) else "", st["meta"]),
                 Paragraph(escape(layout.meta_right[i]) if i < len(layout.meta_right) else "",
                           ParagraphStyle("r", parent=st["meta"], alignment=2))] for i in range(rows)]
        t = Table(data, colWidths=[width / 2, width / 2])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        out.append(t)
    out.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=3, spaceAfter=5))
    return out


def render_pdf(layout: PaperLayout, include_answers: bool) -> bytes:
    _fonts()
    st = _styles()
    buf = BytesIO()
    margin = 16 * mm
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=14 * mm,
                            bottomMargin=16 * mm, title=layout.title, author="SLAYBUS")
    width = A4[0] - 2 * margin

    from app.export.layout import PAPER_TYPE_LABELS
    story: list = _header(layout, st, width, PAPER_TYPE_LABELS.get(layout.paper_type, "Question Paper"))
    if layout.show_student_fields:
        story += [_p("Name: ____________________________   Class/Section: ________   Roll No.: ______", st["meta"]),
                  Spacer(1, 3 * mm)]
    if layout.instructions:
        story.append(_p("General Instructions:", ParagraphStyle("gi", parent=st["meta"], fontName="Serif-Bold")))
        for i, ins in enumerate(layout.instructions, 1):
            story.append(_p(f"{i}. {ins}", st["note"]))
        story.append(Spacer(1, 2 * mm))

    for sec in layout.sections:
        story.append(_p(sec.heading, st["section"]))
        if sec.instructions:
            story.append(_p(sec.instructions, st["note"]))
            story.append(Spacer(1, 2 * mm))
        for q in sec.questions:
            story += _question_block(q, st, width, layout.paper_type)

    if include_answers:
        story.append(PageBreak())
        story += _header(layout, st, width, "Answer Key & Marking Scheme")
        for sec in layout.sections:
            story.append(_p(sec.heading, st["section"]))
            for q in sec.questions:
                story += _answer_block(q, st)

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Serif", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawCentredString(A4[0] / 2, 9 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
