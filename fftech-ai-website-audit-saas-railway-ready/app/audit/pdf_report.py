# -*- coding: utf-8 -*-
"""
fftech-ai-website-audit-saas-railway-ready/app/audit/pdf_report.py
World-class 5-page PDF Website Audit Report Generator
Comprehensive, professional, client-ready with industry-standard metrics
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
    PageBreak, Flowable, KeepInFrame
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart

# Font setup – better Unicode support
try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    BASE_FONT = "DejaVuSans"
except Exception:
    BASE_FONT = "Helvetica"

def get_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name='CoverTitle', fontName=BASE_FONT, fontSize=28, alignment=TA_CENTER, spaceAfter=40, textColor=HexColor('#1e40af')))
    s.add(ParagraphStyle(name='CoverSubtitle', fontName=BASE_FONT, fontSize=16, alignment=TA_CENTER, textColor=colors.grey))
    s.add(ParagraphStyle(name='H1', fontName=BASE_FONT, fontSize=20, spaceBefore=20, spaceAfter=12, textColor=HexColor('#1e3a8a')))
    s.add(ParagraphStyle(name='H2', fontName=BASE_FONT, fontSize=14, spaceBefore=16, spaceAfter=8))
    s.add(ParagraphStyle(name='Body', fontName=BASE_FONT, fontSize=10.5, leading=14))
    s.add(ParagraphStyle(name='Small', fontName=BASE_FONT, fontSize=9, textColor=colors.grey))
    s.add(ParagraphStyle(name='Footer', fontName=BASE_FONT, fontSize=8, textColor=colors.grey, alignment=TA_CENTER))
    return s

class ScoreBar(Flowable):
    def __init__(self, score: Any, width: float = 240, height: float = 24, label: str = ""):
        super().__init__()
        self.score = max(0, min(100, float(score or 0)))
        self.width = width
        self.height = height
        self.label = label

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(HexColor('#e5e7eb'))
        c.rect(0, 0, self.width, self.height, fill=1)
        # Fill
        if self.score >= 90: fill = HexColor('#16a34a')      # dark green
        elif self.score >= 80: fill = HexColor('#22c55e')    # green
        elif self.score >= 70: fill = HexColor('#eab308')    # yellow
        elif self.score >= 50: fill = HexColor('#f97316')    # orange
        else: fill = HexColor('#dc2626')                     # red
        c.setFillColor(fill)
        c.rect(0, 0, self.width * (self.score / 100), self.height, fill=1)
        # Border
        c.setStrokeColor(colors.grey)
        c.rect(0, 0, self.width, self.height)
        # Text
        c.setFillColor(colors.white if self.score < 30 else colors.black)
        c.setFont(BASE_FONT, 12)
        c.drawCentredString(self.width / 2, self.height / 2 - 5, f"{self.label} {int(round(self.score))}%")

def _safe_get(data: Dict, *keys: str, default: Any = "N/A") -> Any:
    cur = data
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k, {})
        else:
            return default
    return default if cur in (None, "", {}) else cur

def _page_cover(audit: Dict, styles) -> List[Any]:
    story = []
    story.append(Spacer(1, 100*mm))
    story.append(Paragraph("Professional Website Audit Report", styles['CoverTitle']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Comprehensive Performance, SEO, Security & UX Analysis", styles['CoverSubtitle']))
    story.append(Spacer(1, 60*mm))

    rows = [
        ["Audited URL", _safe_get(audit, "audited_url", default="N/A")],
        ["Overall Score", f"{_safe_get(audit, 'overall_score', default=0)} / 100 ({_safe_get(audit, 'grade', default='N/A')})"],
        ["Audit Date", _safe_get(audit, "audit_datetime", datetime.now().strftime("%B %d, %Y"))],
        ["Prepared by", _safe_get(audit, "brand_name", "FF Tech AI")],
    ]

    table = Table(rows, colWidths=[70*mm, 90*mm])
    table.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), BASE_FONT, 13),
        ('TEXTCOLOR', (0,0), (0,-1), colors.darkgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), HexColor('#f8f9fa')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
    ]))
    story.append(table)
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("Confidential – For Client Use Only", styles['Small']))
    story.append(PageBreak())
    return story

def _page_summary(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("1. Executive Summary", styles['H1'])]

    overall = _safe_get(audit, "overall_score", default=0)
    grade = _safe_get(audit, "grade", default="N/A")
    risk = _safe_get(audit, "summary", "risk_level", default="Medium")
    impact = _safe_get(audit, "summary", "traffic_impact", default="N/A")

    story.append(ScoreBar(overall, label="Overall Website Health"))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Grade: {grade}  •  Risk Level: {risk}", styles['H2']))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Traffic Impact: {impact}", styles['Body']))

    breakdown = _safe_get(audit, "breakdown", default={})
    scores = [
        ("SEO", _safe_get(breakdown, "seo", "score", default=0)),
        ("Performance", _safe_get(breakdown, "performance", "score", default=0)),
        ("Links & UX", _safe_get(breakdown, "links", "score", default=0)),
        ("Security", _safe_get(breakdown, "security", "score", default=0)),
    ]

    rows = [[cat, ScoreBar(val, width=140, height=12, label=str(int(val)))] for cat, val in scores]
    tbl = Table(rows, colWidths=[80*mm, 80*mm])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(tbl)
    story.append(PageBreak())
    return story

def _page_performance(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("2. Performance & Core Web Vitals", styles['H1'])]

    extras = _safe_get(audit, "breakdown", "performance", "extras", default={})
    rows = [
        ["Load Time", f"{_safe_get(extras, 'load_ms')} ms"],
        ["Page Size", f"{_safe_get(extras, 'bytes'):,} bytes"],
        ["Total Requests", f"{_safe_get(extras, 'total_requests', default='N/A')}"],
        ["Scripts Loaded", _safe_get(extras, "scripts")],
        ["Styles Loaded", _safe_get(extras, "styles")],
        ["Image Formats", _safe_get(extras, "image_formats", "N/A")],
        ["Lazy Loading", _safe_get(extras, "lazy_loading", "N/A")],
        ["Mobile Friendly", _safe_get(extras, "mobile", "mobile_friendly", "N/A")],
    ]

    table = Table(rows, colWidths=[100*mm, 60*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f0f9ff')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightblue),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Priority Recommendations:", styles['H2']))
    for action in _safe_get(audit, "priority_actions", default=[]):
        story.append(Paragraph(f"• {action}", styles['Body']))
    story.append(PageBreak())
    return story

def _page_seo(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("3. SEO & On-Page Optimization", styles['H1'])]

    extras = _safe_get(audit, "breakdown", "seo", "extras", default={})
    rows = [
        ["Page Title", _safe_get(extras, "title") or "Missing / Empty"],
        ["Title Length", f"{len(_safe_get(extras, 'title', default=''))} characters"],
        ["Meta Description", "Present" if _safe_get(extras, "meta_description_present") else "Missing"],
        ["Canonical Tag", _safe_get(extras, "canonical") or "Missing"],
        ["H1 Count", _safe_get(extras, "h1_count")],
        ["Images (Total / Missing ALT)", f"{_safe_get(extras, 'images_total')} / {_safe_get(extras, 'images_missing_alt')}"],
    ]

    table = Table(rows, colWidths=[100*mm, 60*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#fefce8')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.gold),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("SEO Priority Actions:", styles['H2']))
    for action in _safe_get(audit, "priority_actions", default=[]):
        if "SEO" in action or "meta" in action.lower() or "title" in action.lower():
            story.append(Paragraph(f"• {action}", styles['Body']))
    story.append(PageBreak())
    return story

def _page_security(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("4. Security & Technical Audit", styles['H1'])]

    sec = _safe_get(audit, "breakdown", "security", default={})
    rows = [
        ["HTTPS Enforced", "Yes" if sec.get("https") else "No"],
        ["HSTS Enabled", "Yes" if sec.get("hsts") else "No"],
        ["Status Code", str(_safe_get(sec, "status_code"))],
        ["Server Header", _safe_get(sec, "server") or "N/A"],
        ["Security Headers", "Partial / Missing" if not sec.get("hsts") else "Good"],
    ]

    table = Table(rows, colWidths=[100*mm, 60*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#fee2e2')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.red),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Security Recommendations:", styles['H2']))
    for action in _safe_get(audit, "priority_actions", default=[]):
        if "security" in action.lower() or "HSTS" in action or "HTTPS" in action:
            story.append(Paragraph(f"• {action}", styles['Body']))
    story.append(PageBreak())
    return story

def _page_recommendations(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("5. Prioritized Recommendations & Next Steps", styles['H1'])]

    actions = _safe_get(audit, "priority_actions", default=[
        "Optimize images (use WebP/AVIF, lazy loading)",
        "Minify JS/CSS/HTML and reduce total requests",
        "Add unique meta descriptions to all pages",
        "Implement HSTS and modern security headers",
        "Improve color contrast and keyboard navigation for accessibility",
    ])

    for i, action in enumerate(actions[:8], 1):
        story.append(Paragraph(f"{i}. {action}", styles['Body']))

    story.append(Spacer(1, 20))
    story.append(Paragraph("Thank you for using FF Tech Website Audit", styles['H2']))
    story.append(Paragraph("Contact us for implementation support or advanced audits", styles['Small']))
    return story

def generate_audit_pdf(audit: Dict[str, Any]) -> bytes:
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
    story.extend(_page_cover(audit, styles))
    story.extend(_page_summary(audit, styles))
    story.extend(_page_performance(audit, styles))
    story.extend(_page_seo(audit, styles))
    story.extend(_page_security(audit, styles))
    story.extend(_page_recommendations(audit, styles))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

if __name__ == "__main__":
    sample = {
        "audited_url": "https://www.apple.com",
        "overall_score": 92,
        "grade": "A+",
        "audit_datetime": "February 10, 2026",
        "brand_name": "FF Tech AI",
        "breakdown": {
            "performance": {"score": 88, "extras": {"load_ms": 1450, "bytes": 980000, "scripts": 18, "styles": 6, "fetcher": "requests"}},
            "seo": {"score": 95, "extras": {"title": "Apple - Official Site", "meta_description_present": True, "canonical": "https://www.apple.com/", "h1_count": 1, "images_total": 12, "images_missing_alt": 0}},
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
        },
        "summary": {
            "risk_level": "Low",
            "traffic_impact": "Good performance detected"
        },
        "priority_actions": [
            "Optimize hero images with AVIF/WebP format",
            "Add unique meta descriptions to all pages",
            "Enable Strict-Transport-Security (HSTS)",
            "Improve color contrast on buttons/CTAs",
        ]
    }

    pdf_bytes = generate_audit_pdf(sample)
    with open("world-class-website-audit.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("World-class audit report generated: world-class-website-audit.pdf")
