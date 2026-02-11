# -*- coding: utf-8 -*-
"""
World-class Comprehensive Website Audit Report Generator
Professional multi-page PDF with rich visuals, charts, gauges, and modern layout
"""
from __future__ import annotations
from io import BytesIO
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime
import math
import random

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Flowable, Image, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ────────────────────────────────────────────────
# Graphics imports
# ────────────────────────────────────────────────
from reportlab.graphics.shapes import Drawing, String, Line, Circle, Wedge, Rect
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

# ────────────────────────────────────────────────
# Font registration
# ────────────────────────────────────────────────
try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
    BASE_FONT = "DejaVuSans"
    BOLD_FONT = "DejaVuSans-Bold"
except Exception:
    BASE_FONT = "Helvetica"
    BOLD_FONT = "Helvetica-Bold"

# ────────────────────────────────────────────────
# Professional Color Scheme
# ────────────────────────────────────────────────
PRI = HexColor('#1e40af')     # Deep blue - headings, accents
ACC = HexColor('#3b82f6')     # Bright blue - progress
SUC = HexColor('#16a34a')     # Green - good
WAR = HexColor('#eab308')     # Amber - warning
DAN = HexColor('#dc2626')     # Red - critical
NEU = HexColor('#6b7280')     # Neutral gray
BG1 = HexColor('#f8fafc')     # Light background
BG2 = HexColor('#f1f5f9')     # Alternate row
BDR = HexColor('#e2e8f0')     # Borders

# ────────────────────────────────────────────────
# Styles
# ────────────────────────────────────────────────
def get_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle('CoverTitle', fontName=BOLD_FONT, fontSize=34, alignment=TA_CENTER,
                         textColor=PRI, spaceAfter=10, leading=38))
    s.add(ParagraphStyle('CoverSub', fontName=BASE_FONT, fontSize=16, alignment=TA_CENTER,
                         textColor=NEU, spaceAfter=40))
    s.add(ParagraphStyle('H1', fontName=BOLD_FONT, fontSize=22, spaceBefore=28, spaceAfter=10,
                         textColor=PRI))
    s.add(ParagraphStyle('H2', fontName=BOLD_FONT, fontSize=16, spaceBefore=20, spaceAfter=8,
                         textColor=HexColor('#1e293b')))
    s.add(ParagraphStyle('H3', fontName=BOLD_FONT, fontSize=13, spaceBefore=14, spaceAfter=6,
                         textColor=HexColor('#334155')))
    s.add(ParagraphStyle('Body', fontName=BASE_FONT, fontSize=10.8, leading=14.5, alignment=TA_JUSTIFY))
    s.add(ParagraphStyle('Small', fontName=BASE_FONT, fontSize=9.5, textColor=NEU))
    s.add(ParagraphStyle('Badge', fontName=BOLD_FONT, fontSize=10, textColor=colors.white,
                         alignment=TA_CENTER, spacePadding=5))
    s.add(ParagraphStyle('Score', fontName=BOLD_FONT, fontSize=42, alignment=TA_CENTER, textColor=PRI))
    return s

# ────────────────────────────────────────────────
# Visual Components
# ────────────────────────────────────────────────

class ScoreGauge(Flowable):
    """Modern circular gauge for scores"""
    def __init__(self, score: float, label: str = "Score", size=140):
        super().__init__()
        self.score = max(0, min(100, float(score or 0)))
        self.label = label
        self.size = size

    def draw(self):
        c = self.canv
        cx = cy = self.size / 2
        r = self.size * 0.42
        thickness = 18

        # Background arc
        c.setStrokeColor(BG2)
        c.setLineWidth(thickness)
        c.arc(cx-r, cy-r, cx+r, cy+r, -60, 300, fill=0)

        # Progress arc
        progress = (self.score / 100) * 300
        col = SUC if self.score >= 90 else ACC if self.score >= 75 else WAR if self.score >= 60 else DAN
        c.setStrokeColor(col)
        c.arc(cx-r, cy-r, cx+r, cy+r, -60, progress, fill=0)

        # Center text
        c.setFont(BOLD_FONT, 32)
        c.setFillColor(colors.black)
        c.drawCentredString(cx, cy - 12, f"{int(self.score)}")
        c.setFont(BASE_FONT, 12)
        c.setFillColor(NEU)
        c.drawCentredString(cx, cy - 38, self.label)

class ProgressBar(Flowable):
    """Clean horizontal progress bar"""
    def __init__(self, score: float, label: str, width=360, height=26):
        super().__init__()
        self.score = max(0, min(100, float(score or 0)))
        self.label = label
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        # BG
        c.setFillColor(BG1)
        c.rect(0, 0, self.width, self.height, fill=1)
        # Progress
        w = self.width * (self.score / 100)
        col = SUC if self.score >= 90 else ACC if self.score >= 75 else WAR if self.score >= 60 else DAN
        c.setFillColor(col)
        c.rect(0, 0, w, self.height, fill=1)
        # Border
        c.setStrokeColor(BDR)
        c.rect(0, 0, self.width, self.height)
        # Text
        txt_col = colors.white if self.score < 45 else colors.black
        c.setFillColor(txt_col)
        c.setFont(BOLD_FONT, 13)
        c.drawCentredString(self.width/2, self.height/2 - 6, f"{self.label} • {int(self.score)}%")

# Keep / enhance your existing _issue_distribution_pie, _risk_meter, _severity_color, etc.
# (Add them here from your original code or previous version)

# ────────────────────────────────────────────────
# Page 1: Cover
# ────────────────────────────────────────────────
def _page_cover(audit: Dict, styles):
    story = [Spacer(1, 50*mm)]
    # Logo (if provided)
    logo_path = _safe_get(audit, "logo_path")
    if logo_path:
        try:
            img = Image(logo_path, width=90*mm, height=25*mm)
            img.hAlign = 'CENTER'
            story.append(img)
            story.append(Spacer(1, 16*mm))
        except:
            pass

    story.append(Paragraph("Comprehensive Website Audit Report", styles['CoverTitle']))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(_safe_get(audit, "audited_url", "https://example.com"), styles['CoverSub']))
    story.append(Spacer(1, 40*mm))

    meta_data = [
        ["Audit Date (UTC)", _safe_get(audit, "audit_datetime_utc", datetime.utcnow().strftime("%d %b %Y %H:%M UTC"))],
        ["Report ID", _autogen_report_id()],
        ["Prepared By", _safe_get(audit, "brand_name", "Your SaaS Name")],
    ]
    t = Table(meta_data, colWidths=[65*mm, 95*mm])
    t.setStyle(TableStyle([
        ('FONT', (0,0), (0,-1), BOLD_FONT, 12),
        ('FONT', (1,0), (1,-1), BASE_FONT, 12),
        ('TEXTCOLOR', (0,0), (0,-1), NEU),
        ('ALIGN', (0,0), (0,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0, colors.transparent),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 70*mm))
    story.append(Paragraph("Confidential – Client Use Only", styles['Small']))
    story.append(PageBreak())
    return story

# ────────────────────────────────────────────────
# Page 2: Executive Summary
# ────────────────────────────────────────────────
def _page_summary(audit: Dict, styles):
    story = [Paragraph("1. Executive Summary", styles['H1'])]
    overall = _safe_get(audit, "overall_score", 78)
    risk = _safe_get(audit, "summary", "risk_level", "Medium")

    story.append(Spacer(1, 10))
    story.append(ScoreGauge(overall, "Overall Health"))
    story.append(Spacer(1, 16))
    story.append(Paragraph(f"Risk Level: {risk} • Grade: {_letter_grade(overall)}", styles['H3']))

    story.append(Spacer(1, 20))
    for cat, lbl in [("performance","Performance"), ("security","Security"), ("seo","SEO"), ("accessibility","Accessibility")]:
        sc = _safe_get(audit, "breakdown", cat, "score", 70)
        story.append(ProgressBar(sc, lbl))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 20))
    story.append(Paragraph("Top 5 Critical Issues", styles['H2']))
    issues = _safe_get(audit, "issues", [])
    for i, issue in enumerate(sorted(issues, key=lambda x: _risk_to_value(x.get("severity","medium")), reverse=True)[:5], 1):
        sev = issue.get("severity", "Medium")
        col = _severity_color(sev)
        badge_style = ParagraphStyle('Badge', backColor=col)
        story.append(Paragraph(f"{i}. {issue.get('issue_name')} ({sev}) – {issue.get('affected_page','–')}", styles['Body']))

    story.append(Spacer(1, 16))
    pie_and_meter = Table([[_issue_distribution_pie(issues), _risk_meter(risk)]], colWidths=[110*mm, 80*mm])
    story.append(pie_and_meter)
    story.append(PageBreak())
    return story

# Implement remaining pages similarly:
# - Website Overview → clean two-column table
# - Performance → metrics table + bar chart of CWV
# - Security → colored headers table + risk heatmap
# - SEO → status table with impact colors + mini donut/score gauge
# - Accessibility → compliance badge + score gauge
# - Mobile → device compatibility icons/table + score bar
# - UX/UI → radar-like table or colored heuristic scores
# - Compliance → yes/no table with highlights
# - Detailed Issues → per-issue blocks with severity color, code example in monospace box

# ────────────────────────────────────────────────
# Main generator (input/output unchanged)
# ────────────────────────────────────────────────
def generate_audit_pdf(audit: Dict[str, Any]) -> bytes:
    styles = get_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=24*mm, bottomMargin=20*mm)
    story = []
    story += _page_cover(audit, styles)
    story += _page_summary(audit, styles)
    # Add all other _page_... calls here
    # story += _page_overview(...)
    # story += _page_performance(...)
    # ... etc.

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# (Include your original helpers: _safe_get, _yes_no, _letter_grade, _severity_color,
#  _issue_distribution_pie, _risk_meter, _risk_heat_map, etc.)
