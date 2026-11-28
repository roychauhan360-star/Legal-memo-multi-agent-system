"""PDF / Word export for drafts (Function 5) and the PDF report for document analysis (Function 2)."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FOOTER = "DRAFT - for review by a qualified lawyer - not legal advice"
DISCLAIMER = ("AI-assisted document. It is not legal advice and must be reviewed by a qualified Indian lawyer "
              "before any decision, signing or filing.")


def _t(text: str) -> str:
    """Escape for reportlab; swap characters the built-in font cannot draw."""
    text = (text or "").replace("\u20b9", "Rs. ").replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2013", "-").replace("\u2014", "-")
    return escape(text).replace("\n", "<br/>")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontSize=16, alignment=TA_CENTER, spaceAfter=10),
        "body": ParagraphStyle("b", parent=ss["BodyText"], fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=6),
        "small": ParagraphStyle("s", parent=ss["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#444444")),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=4),
    }


def _build(story, title: str, footer_text: str = FOOTER) -> bytes:
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, f"{footer_text}  |  page {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=18 * mm,
                      bottomMargin=20 * mm, title=title).build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ------------------------------------------------------------------ drafts
def draft_to_pdf(draft) -> bytes:
    st = _styles()
    story = [Paragraph(_t(draft.title), st["title"])]
    story += [Paragraph(_t(p), st["body"]) for p in draft.preamble]
    for i, c in enumerate(draft.clauses, 1):
        tag = " <i>[worded by AI from the parties' instructions - check carefully]</i>" if c.ai_drafted else ""
        story.append(Paragraph(f"<b>{i}. {_t(c.heading)}.</b> {_t(c.text)}{tag}", st["body"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("IN WITNESS WHEREOF the parties have signed this document on the date first written above.", st["body"]))

    rows = [[Paragraph(f"<b>{_t(s)}</b><br/><br/><br/>(Signature)<br/>Name: ______________<br/>PAN/ID: ______________", st["small"])
             for s in draft.signatories]]
    table = Table(rows, colWidths=[(A4[0] - 44 * mm) / max(len(draft.signatories), 1)] * len(draft.signatories))
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [Spacer(1, 6), table, Spacer(1, 10)]
    for n in range(1, draft.witnesses + 1):
        story.append(Paragraph(f"Witness {n}: Name ______________  Address ______________  Signature ______________", st["small"]))
        story.append(Spacer(1, 6))

    story += [PageBreak(), Paragraph("SCHEDULE - Description of the property", st["h2"]), Paragraph(_t(draft.schedule_text), st["body"])]
    story += [Spacer(1, 14), Paragraph("Drafting notes for review (remove before signing)", st["h2"])]
    story += [Paragraph("&bull; " + _t(w), st["small"]) for w in draft.warnings]
    return _build(story, draft.title)


def draft_to_docx(draft) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    doc = Document()
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(11.5)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(draft.title)
    run.bold, run.font.size = True, Pt(16)

    for p in draft.preamble:
        para = doc.add_paragraph(p)
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for i, c in enumerate(draft.clauses, 1):
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        para.add_run(f"{i}. {c.heading}. ").bold = True
        para.add_run(c.text)
        if c.ai_drafted:
            para.add_run("  [worded by AI from the parties' instructions - check carefully]").italic = True

    doc.add_paragraph("IN WITNESS WHEREOF the parties have signed this document on the date first written above.")
    table = doc.add_table(rows=1, cols=len(draft.signatories))
    for cell, name in zip(table.rows[0].cells, draft.signatories):
        cell.text = f"{name}\n\n\n(Signature)\nName: ______________\nPAN/ID: ______________"
    for n in range(1, draft.witnesses + 1):
        doc.add_paragraph(f"Witness {n}: Name ______________  Address ______________  Signature ______________")

    doc.add_page_break()
    doc.add_heading("SCHEDULE - Description of the property", level=2)
    doc.add_paragraph(draft.schedule_text)
    doc.add_heading("Drafting notes for review (remove before signing)", level=2)
    for w in draft.warnings:
        doc.add_paragraph(w, style="List Bullet")
    footer = doc.sections[0].footer.paragraphs[0]
    footer.text = FOOTER
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ document analysis report
_CONCERN_COLOR = {"high": "#b91c1c", "medium": "#c2410c", "low": "#a16207", "none": "#15803d"}


def analysis_to_pdf(report: dict, filename: str = "") -> bytes:
    st = _styles()
    story = [Paragraph("Legal Document Analysis", st["title"])]
    if filename:
        story.append(Paragraph(f"Document: {_t(filename)} ({_t(report.get('document_type', ''))})", st["small"]))
    if report.get("truncated"):
        story.append(Paragraph(_t(f"Only the first {report['chars_read']:,} of {report['chars_total']:,} characters were analysed."), st["small"]))

    story += [Paragraph("Summary", st["h2"]), Paragraph(_t(report.get("summary", "")), st["body"])]
    if report.get("key_terms"):
        story.append(Paragraph("Key terms", st["h2"]))
        story += [Paragraph("&bull; " + _t(k), st["small"]) for k in report["key_terms"]]

    if report.get("clauses"):
        story.append(Paragraph("Important clauses", st["h2"]))
        for c in report["clauses"]:
            color = _CONCERN_COLOR.get(c["concern"], "#444444")
            story.append(Paragraph(f'<b>{_t(c["title"])}</b> - <font color="{color}">{c["concern"].upper()}</font>', st["body"]))
            story.append(Paragraph(f'<i>"{_t(c["quote"])}"</i>', st["small"]))
            story.append(Paragraph(_t(c.get("explanation", "")) + (" " + _t(c["concern_reason"]) if c.get("concern_reason") else ""), st["small"]))
            story.append(Spacer(1, 4))

    for heading, key in [("Main concerns", "main_concerns"), ("Possibly missing (keywords not found in the text)", "missing_hints"),
                         ("Questions to ask your lawyer", "questions_for_lawyer")]:
        if report.get(key):
            story.append(Paragraph(heading, st["h2"]))
            story += [Paragraph("&bull; " + _t(x), st["body"]) for x in report[key]]

    if report.get("qa"):
        story.append(Paragraph("Your questions", st["h2"]))
        for qa in report["qa"]:
            story.append(Paragraph(f"<b>Q: {_t(qa['question'])}</b>", st["body"]))
            story.append(Paragraph(_t(qa["answer"]), st["body"]))
            for q in qa.get("quotes", []):
                story.append(Paragraph(f'<i>"{_t(q)}"</i>', st["small"]))

    story += [Spacer(1, 12), Paragraph("<b>Disclaimer.</b> " + _t(DISCLAIMER), st["small"])]
    return _build(story, "Legal Document Analysis", "AI-assisted analysis - not legal advice - review by a qualified lawyer")
