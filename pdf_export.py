"""PDF memo export (reportlab). Uses plain attribute access so it works with any object shaped like the state."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .audit import source_numbers

DISCLAIMER = (
    "This memo was prepared with AI assistance from publicly accessible sources. It is not legal advice and "
    "must be reviewed by a qualified Indian lawyer before any decision or filing. Court records, registers and "
    "unreported matters may not be covered."
)


def _t(text: str) -> str:
    """Escape for reportlab and replace characters the built-in font cannot draw."""
    return escape((text or "").replace("\u20b9", "Rs. ").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"'))


def build_pdf_bytes(state: dict) -> bytes:
    draft = state["draft"]
    sources = state.get("sources", [])
    nums = source_numbers(sources)
    by_id = {s.id: s for s in sources}

    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#444444"))
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=18)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13, spaceBefore=10)

    status = state.get("status", "")
    banner_color = "#1b7f3b" if status == "APPROVED" else "#b45309"
    banner_text = ("All citations verified and quality bar met." if status == "APPROVED"
                   else "NEEDS HUMAN REVIEW: one or more checks did not pass. Do not rely on this memo before a lawyer reviews it.")

    story = [
        Paragraph(_t(draft.title), h1),
        Paragraph(f'<font color="{banner_color}"><b>{_t(status)}</b></font> - {_t(banner_text)}', body),
        Spacer(1, 6),
    ]

    for section in draft.sections:
        story.append(Paragraph(_t(section.heading), h2))
        for claim in section.claims:
            refs = "".join(f"[{nums[i]}]" for i in claim.source_ids if i in nums)
            tag = f' <font color="#1d4ed8">{refs}</font>' if refs else (" <i>(analysis)</i>" if claim.kind == "analysis" else "")
            story.append(Paragraph("&bull; " + _t(claim.text) + tag, body))

    checks = state.get("citation_checks", [])
    if checks:
        story.append(Paragraph("Citation verification", h2))
        rows = [["Case", "Status", "Note"]] + [
            [Paragraph(_t(c.case_name), small), c.status.upper(), Paragraph(_t(c.reason), small)] for c in checks
        ]
        table = Table(rows, colWidths=[60 * mm, 22 * mm, 88 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(table)

    story.append(Paragraph("Sources", h2))
    for sid, n in sorted(nums.items(), key=lambda kv: kv[1]):
        s = by_id[sid]
        story.append(Paragraph(f"[{n}] {_t(s.title or s.id)} - {_t(s.url or 'uploaded document')}", small))

    story += [Spacer(1, 10), Paragraph("<b>Disclaimer.</b> " + _t(DISCLAIMER), small)]

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                      title=draft.title).build(story)
    return buf.getvalue()
