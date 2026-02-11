# -*- coding: utf-8 -*-
"""
fftech-ai-website-audit-saas-railway-ready/app/audit/pdf_report.py
World-class 5-page PDF Website Audit Report Generator
Features:
- Modern, client-ready design
- 5 pages: Cover + Executive Summary + Performance + SEO + Security
- Colored score bars & bar chart visualization
- Safe data access (no crashes)
- Fully compatible with runner.py output structure
"""
from __future__ import annotations
from io import BytesIO
from typing import Any, Dict, List, Tuple
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Flowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend

# ───────────────────────────────────────────────
# Font Setup (better Unicode & emoji support)
# ───────────────────────────────────────────────
try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    BASE_FONT = "DejaVuSans"
except Exception:
    BASE_FONT = "Helvetica"

# ───────────────────────────────────────────────
# Styles
# ───────────────────────────────────────────────
def get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CoverTitle', fontName=BASE_FONT, fontSize=28, leading=34,
        alignment=TA_CENTER, spaceAfter=40, textColor=HexColor('#1e3a8a')
    ))
    styles.add(ParagraphStyle(
        name='CoverSubtitle', fontName=BASE_FONT, fontSize=16, leading=22,
        alignment=TA_CENTER, textColor=colors.grey
    ))
    styles.add(ParagraphStyle(
        name='H1', fontName=BASE_FONT, fontSize=20, leading=24,
        spaceBefore=20, spaceAfter=12, textColor=HexColor('#1e40af')
    ))
    styles.add(ParagraphStyle(
        name='H2', fontName=BASE_FONT, fontSize=14, leading=18,
        spaceBefore=16, spaceAfter=8, textColor=HexColor('#1e3a8a')
    ))
    styles.add(ParagraphStyle(
        name='Body', fontName=BASE_FONT, fontSize=10.5, leading=14,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='Small', fontName=BASE_FONT, fontSize=9, leading=12,
        textColor=colors.grey
    ))
    styles.add(ParagraphStyle(
        name='ScoreLabel', fontName=BASE_FONT, fontSize=12, alignment=TA_CENTER
    ))
    return styles

# ───────────────────────────────────────────────
# Colored Score Bar Component
# ───────────────────────────────────────────────
class ScoreBar(Flowable):
    def __init__(self, score: float, width: float = 220, height: float = 20, label: str = ""):
        super().__init__()
        self.score = max(0, min(100, float(score or 0)))
        self.width = width
        self.height = height
        self.label = label

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(HexColor('#e5e7eb'))
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        # Progress bar color
        if self.score >= 85:
            color = HexColor('#22c55e')  # green
        elif self.score >= 70:
            color = HexColor('#eab308')  # yellow
        else:
            color = HexColor('#ef4444')  # red

        c.setFillColor(color)
        c.rect(0, 0, self.width * (self.score / 100), self.height, fill=1, stroke=0)

        # Border
        c.setStrokeColor(colors.grey)
        c.rect(0, 0, self.width, self.height, fill=0)

        # Text
        c.setFillColor(colors.black)
        c.setFont(BASE_FONT, 11)
        c.drawCentredString(self.width / 2, self.height / 2 - 4, f"{self.label} {int(round(self.score))}%")

# ───────────────────────────────────────────────
# Bar Chart Component (Score Breakdown)
# ───────────────────────────────────────────────
class ScoreChart(Flowable):
    def __init__(self, categories: List[Tuple[str, float]], width: float = 400, height: float = 200):
        super().__init__()
        self.categories = categories  # e.g. [("SEO", 95), ("Performance", 88), ...]
        self.width = width
        self.height = height

    def draw(self):
        d = Drawing(self.width, self.height)

        bc = VerticalBarChart()
        bc.x = 50
        bc.y = 50
        bc.width = self.width - 100
        bc.height = self.height - 80

        bc.categoryNames = [cat[0] for cat in self.categories]
        bc.data = [[cat[1] for cat in self.categories]]

        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20

        bc.categoryAxis.labels.boxAnchor = 'n'
        bc.categoryAxis.labels.dx = 0
        bc.categoryAxis.labels.dy = -10

        # Colors
        bc.bars[0].fillColor = HexColor('#6366f1')  # indigo

        d.add(bc)

        # Title
        title = String(self.width/2, self.height - 20, "Score Breakdown", fillColor=HexColor('#1e3a8a'), fontSize=14, textAnchor='middle')
        d.add(title)

        d.drawOn(self.canv, 0, 0)

# ───────────────────────────────────────────────
# Safe Get Helper
# ───────────────────────────────────────────────
def _safe_get(data: Dict, *keys: str, default: Any = "N/A") -> Any:
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, {})
        else:
            return default
    return default if current in (None, "", {}) else current

# ───────────────────────────────────────────────
# Page 1 – Cover Page
# ───────────────────────────────────────────────
def _page_cover(audit: Dict, styles) -> List[Any]:
    story = []
    story.append(Spacer(1, 80*mm))

    title = Paragraph("Website Audit Report", styles['CoverTitle'])
    story.append(title)

    subtitle = Paragraph("Professional Website Performance & SEO Analysis", styles['CoverSubtitle'])
    story.append(subtitle)

    story.append(Spacer(1, 40*mm))

    url = _safe_get(audit, "audited_url", default="N/A")
    score = _safe_get(audit, "overall_score", default=0)
    grade = _safe_get(audit, "grade", default="N/A")
    date = _safe_get(audit, "audit_datetime", datetime.now().strftime("%B %d, %Y"))

    meta = [
        ["Audited URL", url],
        ["Overall Score", f"{score}/100 ({grade})"],
        ["Generated on", date],
        ["Prepared by", _safe_get(audit, "brand_name", "FF Tech")],
    ]

    table = Table(meta, colWidths=[60*mm, 100*mm])
    table.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), BASE_FONT, 12),
        ('TEXTCOLOR', (0,0), (0,-1), colors.darkgrey),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), HexColor('#f8f9fa')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(KeepTogether(table))

    story.append(Spacer(1, 20*mm))
    story.append(Paragraph("Confidential – For Client Use Only", styles['Small']))
    story.append(PageBreak())
    return story

# ───────────────────────────────────────────────
# Page 2 – Executive Summary
# ───────────────────────────────────────────────
def _page_summary(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("Executive Summary", styles['H1'])]

    overall = _safe_get(audit, "overall_score", default=0)
    story.append(ScoreBar(overall, label="Overall Score"))
    story.append(Spacer(1, 12))

    breakdown = _safe_get(audit, "breakdown", default={})
    scores = [
        ("SEO", _safe_get(breakdown, "seo", "score", default=0)),
        ("Performance", _safe_get(breakdown, "performance", "score", default=0)),
        ("Links", _safe_get(breakdown, "links", "score", default=0)),
        ("Security", _safe_get(breakdown, "security", "score", default=0)),
    ]

    chart = ScoreChart(scores)
    story.append(chart)
    story.append(Spacer(1, 16))

    verdict = "Excellent" if overall >= 90 else "Good" if overall >= 75 else "Needs Improvement"
    story.append(Paragraph(f"Overall Verdict: {verdict}", styles['H2']))
    story.append(PageBreak())
    return story

# ───────────────────────────────────────────────
# Page 3 – Performance & Technical Details
# ───────────────────────────────────────────────
def _page_performance(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("Performance Analysis", styles['H1'])]

    extras = _safe_get(audit, "breakdown", "performance", "extras", default={})
    rows = [
        ["Load Time", f"{_safe_get(extras, 'load_ms')} ms"],
        ["Page Size", f"{_safe_get(extras, 'bytes'):,} bytes"],
        ["Scripts", _safe_get(extras, "scripts")],
        ["Styles", _safe_get(extras, "styles")],
        ["Fetcher", _safe_get(extras, "fetcher")],
    ]

    table = Table(rows, colWidths=[90*mm, 70*mm])
    table.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), BASE_FONT, 11),
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(table)
    story.append(PageBreak())
    return story

# ───────────────────────────────────────────────
# Page 4 – SEO & On-Page Analysis
# ───────────────────────────────────────────────
def _page_seo(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("SEO & On-Page Analysis", styles['H1'])]

    extras = _safe_get(audit, "breakdown", "seo", "extras", default={})
    rows = [
        ["Page Title", _safe_get(extras, "title") or "N/A"],
        ["Meta Description", "Present" if _safe_get(extras, "meta_description_present") else "Missing"],
        ["Canonical URL", _safe_get(extras, "canonical") or "Missing"],
        ["H1 Tags", _safe_get(extras, "h1_count")],
        ["Images (Total / Missing ALT)", f"{_safe_get(extras, 'images_total')} / {_safe_get(extras, 'images_missing_alt')}"],
    ]

    table = Table(rows, colWidths=[90*mm, 70*mm])
    table.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), BASE_FONT, 11),
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(table)
    story.append(PageBreak())
    return story

# ───────────────────────────────────────────────
# Page 5 – Security & Technical Details
# ───────────────────────────────────────────────
def _page_security(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("Security & Technical Details", styles['H1'])]

    sec = _safe_get(audit, "breakdown", "security", default={})
    rows = [
        ["HTTPS Enabled", "Yes" if sec.get("https") else "No"],
        ["HSTS Header", "Yes" if sec.get("hsts") else "No"],
        ["Status Code", str(_safe_get(sec, "status_code"))],
        ["Server", _safe_get(sec, "server") or "N/A"],
    ]

    table = Table(rows, colWidths=[90*mm, 70*mm])
    table.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), BASE_FONT, 11),
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(table)

    story.append(Spacer(1, 20))
    story.append(Paragraph("Audit powered by FF Tech AI", styles['Small']))
    return story

# ───────────────────────────────────────────────
# Main PDF Generation Function
# ───────────────────────────────────────────────
def generate_audit_pdf(audit: Dict[str, Any]) -> bytes:
    """
    Generates a professional 5-page website audit PDF.
    Input: dict from runner_result_to_audit_data()
    Output: PDF bytes (ready for file or HTTP response)
    """
    styles = get_styles()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=20*mm,
    )

    story = []

    # Page 1: Cover
    story.extend(_page_cover(audit, styles))

    # Page 2: Executive Summary + Chart
    story.extend(_page_summary(audit, styles))

    # Page 3: Performance
    story.extend(_page_performance(audit, styles))

    # Page 4: SEO
    story.extend(_page_seo(audit, styles))

    # Page 5: Security
    story.extend(_page_security(audit, styles))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes

# ───────────────────────────────────────────────
# Local Test (run file directly)
# ───────────────────────────────────────────────
if __name__ == "__main__":
    sample = {
        "audited_url": "https://www.apple.com",
        "overall_score": 92,
        "grade": "A+",
        "breakdown": {
            "performance": {"score": 88, "extras": {"load_ms": 1450, "bytes": 980000, "scripts": 18, "styles": 6, "fetcher": "requests"}},
            "seo": {"score": 95, "extras": {"title": "Apple", "meta_description_present": True, "canonical": "https://www.apple.com/", "h1_count": 1, "images_total": 12, "images_missing_alt": 0}},
            "security": {"score": 92, "https": True, "hsts": True, "status_code": 200, "server": "Apple CDN"},
            "links": {"score": 90},
        },
        "dynamic": {
            "cards": [
                {"title": "Page Title", "body": "Apple - Official Site"},
                {"title": "Load Time", "body": "1450 ms"},
            ],
            "kv": [
                {"key": "HTTPS", "value": True},
                {"key": "HSTS", "value": True},
                {"key": "Images Missing ALT", "value": 0},
            ]
        }
    }

    pdf_bytes = generate_audit_pdf(sample)
    with open("world-class-audit-report.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("World-class 5-page audit report saved: world-class-audit-report.pdf")
