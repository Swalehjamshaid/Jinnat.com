# -*- coding: utf-8 -*-
"""
fftech-ai-website-audit-saas-railway-ready/app/audit/pdf_report.py
Professional PDF report generator for website audits
Compatible with runner.py data structure
"""
from __future__ import annotations
from io import BytesIO
from typing import Any, Dict, List
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Font setup
try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    BASE_FONT = "DejaVuSans"
except Exception:
    BASE_FONT = "Helvetica"


def _styles() -> Dict[str, ParagraphStyle]:
    """
    Build a stylesheet with unique names to avoid collisions with ReportLab defaults.
    """
    s = getSampleStyleSheet()

    # Create uniquely-named styles so we don't collide with built-ins like "Title"
    s.add(ParagraphStyle(name="TitleX", fontName=BASE_FONT, fontSize=22, alignment=TA_CENTER, spaceAfter=18))
    s.add(ParagraphStyle(name="H1X", fontName=BASE_FONT, fontSize=16, spaceBefore=14, spaceAfter=10))
    s.add(ParagraphStyle(name="H2X", fontName=BASE_FONT, fontSize=13, spaceBefore=12, spaceAfter=8))
    s.add(ParagraphStyle(name="BodyX", fontName=BASE_FONT, fontSize=10.5, leading=14))
    s.add(ParagraphStyle(name="SmallX", fontName=BASE_FONT, fontSize=9, textColor=colors.grey))
    s.add(ParagraphStyle(name="CenterX", fontName=BASE_FONT, fontSize=10.5, alignment=TA_CENTER))
    return s


class ScoreBar(Flowable):
    def __init__(self, score: Any, width: float = 160, height: float = 12, label: str = ""):
        super().__init__()
        try:
            sval = float(score or 0)
        except Exception:
            sval = 0.0
        self.score = max(0.0, min(100.0, sval))
        self.width = width
        self.height = height
        self.label = label

    def draw(self):
        c = self.canv
        # Border
        c.setStrokeColor(colors.lightgrey)
        c.rect(0, 0, self.width, self.height, stroke=1, fill=0)
        # Fill color by score
        if self.score >= 85:
            fill = colors.green
        elif self.score >= 70:
            fill = colors.orange
        else:
            fill = colors.red
        c.setFillColor(fill)
        c.rect(0, 0, self.width * (self.score / 100.0), self.height, stroke=0, fill=1)
        # Text label
        if self.label:
            c.setFillColor(colors.black)
            c.setFont(BASE_FONT, 10)
            c.drawString(self.width + 10, 2, f"{self.label}: {int(self.score)}")


def _safe_get(data: Dict, *keys: str, default: Any = "N/A") -> Any:
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, {})
        else:
            return default
    return default if current in (None, "", {}) else current


def _fmt_value(v: Any, suffix: str = "") -> str:
    """
    Format numbers with thousands separators; pass through strings; handle None as N/A.
    """
    if v in (None, "", {}):
        return "N/A"
    try:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return f"{int(v):,}{(' ' + suffix) if suffix else ''}"
    except Exception:
        pass
    return f"{v}{(' ' + suffix) if suffix and v not in ('N/A', '') else ''}"


def _header(audit: Dict, styles) -> List[Any]:
    story = []
    story.append(Paragraph("Website Audit Report", styles["TitleX"]))

    url = _safe_get(audit, "audited_url", default="N/A")
    score = _safe_get(audit, "overall_score", default=0)
    grade = _safe_get(audit, "grade", default="N/A")
    date = datetime.now().strftime("%B %d, %Y")

    rows = [
        ["Audited URL", url],
        ["Overall Score", f"{_fmt_value(score)}/100  ({grade})"],
        ["Generated on", date],
    ]
    table = Table(rows, colWidths=[55 * mm, 105 * mm])
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), BASE_FONT, 11),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.darkgrey),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8f9fa")),
    ]))
    story.append(table)
    story.append(Spacer(1, 14))
    return story


def _executive_summary(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("Executive Summary", styles["H1X"])]

    overall = _safe_get(audit, "overall_score", default=0)
    story.append(ScoreBar(overall, width=220, height=16, label="Overall Health"))

    story.append(Spacer(1, 12))

    breakdown = _safe_get(audit, "breakdown", default={})
    cats = [
        ("SEO", _safe_get(breakdown, "seo", "score", default=0)),
        ("Performance", _safe_get(breakdown, "performance", "score", default=0)),
        ("Links", _safe_get(breakdown, "links", "score", default=0)),
        ("Security", _safe_get(breakdown, "security", "score", default=0)),
    ]

    rows = [[name, ScoreBar(score, width=140, height=10, label=str(int(score)))] for name, score in cats]
    tbl = Table(rows, colWidths=[65 * mm, 95 * mm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
    ]))
    story.append(tbl)

    story.append(PageBreak())
    return story


def _section(title: str, rows: List[List[Any]], styles, col_widths=None) -> List[Any]:
    story = [Paragraph(title, styles["H1X"])]
    if not rows:
        story.append(Paragraph("No data available", styles["SmallX"]))
    else:
        default_widths = [65 * mm, 95 * mm] if col_widths is None else col_widths
        tbl = Table(rows, colWidths=default_widths)
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tbl)
    story.append(PageBreak())
    return story


def _performance(audit: Dict, styles) -> List[Any]:
    extras = _safe_get(audit, "breakdown", "performance", "extras", default={})
    rows = [
        ["Load Time", f"{_fmt_value(extras.get('load_ms'))} ms"],
        ["Page Size", _fmt_value(extras.get("bytes"), "bytes")],
        ["Scripts count", _fmt_value(extras.get("scripts"))],
        ["Styles count", _fmt_value(extras.get("styles"))],
        ["Fetcher used", _fmt_value(extras.get("fetcher"))],
    ]
    return _section("Performance", rows, styles)


def _seo(audit: Dict, styles) -> List[Any]:
    extras = _safe_get(audit, "breakdown", "seo", "extras", default={})
    rows = [
        ["Page Title", _fmt_value(extras.get("title"))],
        ["Meta Description", "Present" if extras.get("meta_description_present") else "Missing"],
        ["Canonical Tag", extras.get("canonical", "") or "Missing"],
        ["H1 Count", _fmt_value(extras.get("h1_count"))],
        ["Images (Total / No ALT)", f"{_fmt_value(extras.get('images_total'))} / {_fmt_value(extras.get('images_missing_alt'))}"],
    ]
    return _section("SEO", rows, styles)


def _security(audit: Dict, styles) -> List[Any]:
    sec = _safe_get(audit, "breakdown", "security", default={})
    rows = [
        ["HTTPS", "Yes" if sec.get("https") else "No"],
        ["HSTS", "Yes" if sec.get("hsts") else "No"],
        ["Status Code", _fmt_value(sec.get("status_code"))],
        ["Server Header", _fmt_value(sec.get("server"))],
    ]
    return _section("Security", rows, styles)


def _dynamic_info(audit: Dict, styles) -> List[Any]:
    dyn = _safe_get(audit, "dynamic", default={})
    story = [Paragraph("Additional Details", styles["H1X"])]

    cards = dyn.get("cards", []) or []
    if cards:
        story.append(Paragraph("Highlights", styles["H2X"]))
        rows = [[(c.get("title", "N/A")), (c.get("body", "N/A"))] for c in cards[:6]]
        tbl = Table(rows, colWidths=[70 * mm, 90 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3f2fd")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightblue),
        ]))
        story.append(tbl)

    kv = dyn.get("kv", []) or []
    if kv:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Key Information", styles["H2X"]))
        rows = [[item.get("key", "N/A"), _fmt_value(item.get("value"))] for item in kv]
        tbl = Table(rows, colWidths=[70 * mm, 90 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ]))
        story.append(tbl)

    story.append(PageBreak())
    return story


def generate_audit_pdf(audit: Dict[str, Any]) -> bytes:
    """
    Generate professional PDF audit report.
    Works with data from runner.py (safe access, defaults everywhere).
    Returns PDF bytes.
    """
    styles = _styles()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    story: List[Any] = []
    story.extend(_header(audit, styles))
    story.extend(_executive_summary(audit, styles))
    story.extend(_performance(audit, styles))
    story.extend(_seo(audit, styles))
    story.extend(_security(audit, styles))
    story.extend(_dynamic_info(audit, styles))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ───────────────────────────────────────────────
# Local test
# ───────────────────────────────────────────────
if __name__ == "__main__":
    sample = {
        "audited_url": "https://www.apple.com",
        "overall_score": 92,
        "grade": "A+",
        "breakdown": {
            "seo": {"score": 95, "extras": {"title": "Apple", "meta_description_present": True, "h1_count": 1, "images_total": 10, "images_missing_alt": 1, "canonical": "https://www.apple.com/"}},
            "performance": {"score": 88, "extras": {"load_ms": 1200, "bytes": 950000, "scripts": 12, "styles": 5, "fetcher": "requests"}},
            "security": {"score": 90, "https": True, "hsts": True, "status_code": 200, "server": "nginx"},
        },
        "dynamic": {
            "cards": [
                {"title": "Page Title", "body": "Apple - Official Site"},
                {"title": "Load Time", "body": "1200 ms"},
            ],
            "kv": [
                {"key": "HTTPS", "value": True},
                {"key": "Fetcher", "value": "requests"},
            ]
        }
    }

    pdf = generate_audit_pdf(sample)
    with open("audit-report-refined.pdf", "wb") as f:
        f.write(pdf)
    print("Refined sample PDF saved: audit-report-refined.pdf")
``
