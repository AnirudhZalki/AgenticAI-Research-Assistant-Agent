"""
IEEE-style two-column PDF typesetter with REAL page counting.

Takes the draft sections (plain-text markup produced by DraftingWritingAgent) and typesets them like a conference
paper: title block, abstract, Roman-numbered sections, tables, numbered references, page footer. Because ReportLab does
the layout itself, the page count is exact (no estimation), which lets the coordinator fit the paper to the venue's
page range (e.g. 6-8 pages) by choosing how much evidence-derived material to include.

Markup understood inside a section's text:
    "### Heading"                  sub-heading
    lines starting with "|"        table (first row = header)
    "[[BOX: label | height_in]]"   reserved empty box for the authors' figure (counted as reserved space)
    "- item" / "  - item"          bullet
    "[AUTHORS TO ... ]"            highlighted placeholder (nothing is invented for it)
"""

import io
import re
from typing import Any, Dict, List, Tuple
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, FrameBreak, Frame, Flowable, NextPageTemplate, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

PAGE_W, PAGE_H = letter
L_MARGIN = R_MARGIN = 0.625 * inch
TOP, BOTTOM = 0.75 * inch, 1.0 * inch
GUTTER = 0.25 * inch
COL_W = (PAGE_W - L_MARGIN - R_MARGIN - GUTTER) / 2
BODY_H = PAGE_H - TOP - BOTTOM
TITLE_H = 1.55 * inch

_MAP = {"→": "->", "←": "<-", "‖": "||", "×": "x", "≥": ">=", "≤": "<=",
        "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...",
        "·": "-", "−": "-", " ": " "}


def pdf_text(s: Any) -> str:
    t = "".join(_MAP.get(c, c) for c in str(s))
    return t.encode("cp1252", "replace").decode("cp1252")


S = {
    "body": ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=11.6, alignment=4, spaceAfter=4),
    "bullet": ParagraphStyle("bullet", fontName="Times-Roman", fontSize=10, leading=11.6, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "h1": ParagraphStyle("h1", fontName="Times-Bold", fontSize=10, leading=12, alignment=1, spaceBefore=8, spaceAfter=4),
    "h2": ParagraphStyle("h2", fontName="Times-BoldItalic", fontSize=10, leading=11.6, spaceBefore=4, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="Times-Bold", fontSize=20, leading=23, alignment=1, spaceAfter=6),
    "author": ParagraphStyle("author", fontName="Times-Roman", fontSize=11, leading=13, alignment=1),
    "affil": ParagraphStyle("affil", fontName="Times-Italic", fontSize=9, leading=11, alignment=1, textColor=colors.HexColor("#444444")),
    "abstract": ParagraphStyle("abstract", fontName="Times-Bold", fontSize=9, leading=10.5, alignment=4, spaceAfter=4),
    "tag": ParagraphStyle("tag", fontName="Times-Italic", fontSize=7.5, leading=9, textColor=colors.HexColor("#777777"), spaceAfter=2),
    "ref": ParagraphStyle("ref", fontName="Times-Roman", fontSize=8, leading=9.2, leftIndent=18, firstLineIndent=-18, spaceAfter=1.5),
    "cell": ParagraphStyle("cell", fontName="Times-Roman", fontSize=7.5, leading=8.6),
    "cellh": ParagraphStyle("cellh", fontName="Times-Bold", fontSize=7.5, leading=8.6),
}


class ReservedBox(Flowable):
    """Dashed empty box that keeps room for a figure the authors will add. Recorded so reserved space is reported."""
    registry: List[float] = []

    def __init__(self, label: str, height_in: float):
        super().__init__()
        self.label, self.h = label, height_in * inch

    def wrap(self, aw, ah):
        self.width = aw
        return aw, self.h

    def draw(self):
        c = self.canv
        c.setDash(3, 2)
        c.setStrokeColor(colors.HexColor("#888888"))
        c.rect(0, 0, self.width, self.h - 4)
        c.setDash()
        c.setFont("Times-Italic", 8)
        c.setFillColor(colors.HexColor("#666666"))
        words, lines, cur = pdf_text(self.label).split(), [], ""
        for w in words:                                   # wrap the label inside the box
            if len(cur) + len(w) + 1 > 52:
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        lines.append(cur)
        y = self.h / 2 + 5 * (len(lines) - 1)
        for ln in lines:
            c.drawCentredString(self.width / 2, y, ln)
            y -= 10


def _highlight(text: str) -> str:
    """Escape for ReportLab and highlight [AUTHORS TO ...] placeholders (bracket-depth aware)."""
    out, i = [], 0
    while i < len(text):
        j = text.find("[AUTHORS TO", i)
        if j < 0:
            out.append(escape(text[i:]))
            break
        out.append(escape(text[i:j]))
        depth, k = 0, j
        while k < len(text):
            depth += text[k] == "["
            depth -= text[k] == "]"
            k += 1
            if depth == 0:
                break
        out.append('<font backColor="#fff2b3"><i>' + escape(text[j:k]) + "</i></font>")
        i = k
    return "".join(out)


def _table(rows: List[List[str]]) -> Table:
    n = max(len(r) for r in rows)
    head = str(rows[0][0]) if rows else ""
    widths = {2: [0.75, 2.75], 3: [0.95, 1.2, 1.35], 4: [0.5, 0.5, 1.5, 1.0], 5: [0.42, 0.4, 1.35, 0.8, 0.53]}.get(n)
    if head == "Method" and n == 4:
        widths = [0.85, 0.85, 0.9, 0.9]
    if head == "Variant":
        widths = [0.95, 0.55, 0.6, 0.6, 0.8][:n]
    cw = [w * inch for w in widths] if widths else [COL_W / n] * n
    data = []
    for ri, r in enumerate(rows):
        r = r + [""] * (n - len(r))
        data.append([Paragraph(_highlight(pdf_text(c)), S["cellh" if ri == 0 else "cell"]) for c in r])
    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.black), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    return t


def _section_flowables(title: str, text: str, idx: int) -> Tuple[List[Flowable], float]:
    flow: List[Flowable] = []
    reserved = 0.0
    head = re.sub(r"^\d+\.\s*", "", title).upper()
    flow.append(Paragraph(pdf_text(f"{_roman(idx)}. {head}"), S["h1"]))
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        s = ln.strip()
        if not s:
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split(" | ")])
                i += 1
            flow.append(_table(rows))
            flow.append(Spacer(1, 4))
            continue
        i += 1
        m = re.match(r"\[\[BOX:\s*(.*?)\s*\|\s*([\d.]+)\s*\]\]", s)
        if m:
            h = float(m.group(2))
            flow.append(ReservedBox(m.group(1), h))
            flow.append(Spacer(1, 4))
            reserved += h * inch + 4
        elif s.startswith("###"):
            flow.append(Paragraph(pdf_text(s[3:].strip()), S["h2"]))
        elif s.startswith("[AI-DRAFTED"):
            flow.append(Paragraph(pdf_text(s), S["tag"]))
        elif re.match(r"^-\s+", s):
            flow.append(Paragraph(_highlight(pdf_text(re.sub(r"^-\s+", "", s))), S["bullet"], bulletText="•"))
        else:
            flow.append(Paragraph(_highlight(pdf_text(s)), S["body"]))
    return flow, reserved


def _roman(n: int) -> str:
    out = ""
    for v, r in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out, n = out + r, n - v
    return out


def render_pdf(ctx: Dict[str, Any], title: str = "", authors: List[str] = None) -> Dict[str, Any]:
    """Typeset the current draft. Returns {"pdf": bytes, "pages": int, "reserved_pages": float, ...}."""
    buf = io.BytesIO()
    authors = authors or [a.strip() for a in str(ctx.get("collaborators", "")).split(",") if a.strip()]
    title = title or f"A Systematic Investigation into {str(ctx.get('topic', '')).title()}"

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(PAGE_W / 2, 0.5 * inch, pdf_text(f"DRAFT - pending faculty review  |  Page {doc.page}"))
        canvas.restoreState()

    doc = BaseDocTemplate(buf, pagesize=letter, leftMargin=L_MARGIN, rightMargin=R_MARGIN, topMargin=TOP, bottomMargin=BOTTOM,
                          title=pdf_text(title), author=pdf_text(", ".join(authors)))
    top_y = PAGE_H - TOP
    first = PageTemplate(id="first", onPage=footer, frames=[
        Frame(L_MARGIN, top_y - TITLE_H, PAGE_W - L_MARGIN - R_MARGIN, TITLE_H, id="title", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        Frame(L_MARGIN, BOTTOM, COL_W, BODY_H - TITLE_H, id="c1", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        Frame(L_MARGIN + COL_W + GUTTER, BOTTOM, COL_W, BODY_H - TITLE_H, id="c2", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)])
    later = PageTemplate(id="later", onPage=footer, frames=[
        Frame(L_MARGIN, BOTTOM, COL_W, BODY_H, id="c1", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        Frame(L_MARGIN + COL_W + GUTTER, BOTTOM, COL_W, BODY_H, id="c2", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)])
    doc.addPageTemplates([first, later])

    gap = ctx.get("gap_analysis", {})
    refs = ctx.get("reading_list", [])
    abstract = (f"Abstract—{gap.get('novelty_summary', '')} The study draws on {len(refs)} retrieved papers"
                f" ({', '.join(sorted({p['source'].split(' ')[0] for p in refs}))}). "
                "Methods and results are to be provided by the authors; this draft makes no experimental claims.")
    keywords = ", ".join(dict.fromkeys(re.findall(r"[A-Za-z][A-Za-z\-]{2,}", str(ctx.get("topic", "")))))
    story: List[Flowable] = [Paragraph(pdf_text(title), S["title"]),
                             Paragraph(pdf_text(", ".join(authors) or "Authors"), S["author"]),
                             Paragraph("Draft assembled by the Research Assistant Agent - AI-drafted, pending faculty review", S["affil"]),
                             FrameBreak(), NextPageTemplate("later"),
                             Paragraph(_highlight(pdf_text(abstract)), S["abstract"]),
                             Paragraph(pdf_text(f"Index Terms—{keywords}"), S["abstract"])]
    reserved = 0.0
    for i, (sec_title, text) in enumerate(ctx.get("draft_sections", {}).items(), 1):
        flow, r = _section_flowables(sec_title, text, i)
        story += flow
        reserved += r
    story.append(Paragraph("REFERENCES", S["h1"]))
    for r in ctx.get("formatted_references", []):
        story.append(Paragraph(_highlight(pdf_text(r)), S["ref"]))
    doc.build(story)
    pages = doc.page
    page_area = 2 * BODY_H
    return {"pdf": buf.getvalue(), "pages": pages, "reserved_pages": round(reserved / page_area, 2),
            "reserved_inches": round(reserved / inch, 1)}
