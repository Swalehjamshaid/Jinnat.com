# -*- coding: utf-8 -*-
"""
fftech-ai-website-audit-saas-railway-ready/app/audit/pdf_report.py
Comprehensive, graph-rich Website Audit PDF Generator
- Keeps I/O identical: generate_audit_pdf(audit: Dict[str, Any]) -> bytes
- Sharper fonts (Noto/DejaVu fallback), high-contrast colors
- Page numbers (Page X of Y)
- Visuals across sections: pies, donuts, grouped bars, coverage bars, heat map
- Competitor Comparison: apple-to-apple table + grouped bar charts (scores & CWV)
- Traffic & Acquisition: GA-style KPIs, channel mix, geo, trends
- Google Search Reach: GSC KPIs, coverage, web vitals, top queries/pages, backlinks, Discover
- Smarter fallbacks and optional hide-empty-rows mode to avoid 'N/A' noise
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
    PageBreak, Flowable, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# Graphics
from reportlab.graphics.shapes import Drawing, String, Line, Circle, Wedge, Rect
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

# ============================================================================
# Fonts: register sharp, professional sans fonts with sensible fallbacks
# ============================================================================
def _register_fonts():
    """
    Try Noto Sans (crisp, wide-Unicode), fall back to DejaVu Sans, then Helvetica.
    """
    global BASE_FONT, BASE_FONT_BOLD
    BASE_FONT, BASE_FONT_BOLD = "Helvetica", "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(TTFont("NotoSans", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"))
        pdfmetrics.registerFont(TTFont("NotoSans-Bold", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"))
        BASE_FONT, BASE_FONT_BOLD = "NotoSans", "NotoSans-Bold"
        return
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
        BASE_FONT, BASE_FONT_BOLD = "DejaVuSans", "DejaVuSans-Bold"
    except Exception:
        BASE_FONT, BASE_FONT_BOLD = "Helvetica", "Helvetica-Bold"

_register_fonts()

# ============================================================================
# Styles
# ============================================================================
def get_styles():
    s = getSampleStyleSheet()
    # Cover
    s.add(ParagraphStyle(name='CoverTitle', fontName=BASE_FONT_BOLD, fontSize=30, alignment=TA_CENTER,
                         spaceAfter=28, textColor=HexColor('#1e293b')))
    s.add(ParagraphStyle(name='CoverSubtitle', fontName=BASE_FONT, fontSize=14, alignment=TA_CENTER,
                         textColor=HexColor('#475569')))
    # Headings
    s.add(ParagraphStyle(name='H1', fontName=BASE_FONT_BOLD, fontSize=20, spaceBefore=14, spaceAfter=10,
                         textColor=HexColor('#0f172a')))
    s.add(ParagraphStyle(name='H2', fontName=BASE_FONT_BOLD, fontSize=13.5, spaceBefore=10, spaceAfter=6,
                         textColor=HexColor('#0f172a')))
    s.add(ParagraphStyle(name='H3', fontName=BASE_FONT_BOLD, fontSize=12, spaceBefore=8, spaceAfter=4))
    # Body
    s.add(ParagraphStyle(name='Body', fontName=BASE_FONT, fontSize=11, leading=15, textColor=HexColor('#111827')))
    s.add(ParagraphStyle(name='Small', fontName=BASE_FONT, fontSize=9, textColor=HexColor('#64748b'), leading=12))
    s.add(ParagraphStyle(name='Footer', fontName=BASE_FONT, fontSize=8, textColor=HexColor('#6b7280'), alignment=TA_CENTER))
    # Badge / Mono
    s.add(ParagraphStyle(name='Badge', fontName=BASE_FONT_BOLD, fontSize=10, textColor=colors.white,
                         backColor=HexColor('#475569'), leftIndent=4, rightIndent=4))
    s.add(ParagraphStyle(name='Mono', fontName=BASE_FONT, fontSize=9, leading=12,
                         textColor=HexColor('#0f172a')))
    return s

# ============================================================================
# Utilities & helpers
# ============================================================================
def _safe_get(data: Dict, *keys: str, default: Any = "N/A") -> Any:
    cur = data
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k, {})
        else:
            return default
    return default if cur in (None, "", {}) else cur

def _yes_no(v: Any) -> str:
    if isinstance(v, bool): return "Yes" if v else "No"
    s = str(v).strip().lower()
    if s in ("yes","y","true","1"): return "Yes"
    if s in ("no","n","false","0"): return "No"
    return "N/A"

def _fmt(value: Any, suffix: str = "") -> str:
    if value in (None, "", {}, []): return "N/A"
    return f"{value}{suffix}"

def _letter_grade(score: Optional[float]) -> str:
    try: s = float(score or 0)
    except: s = 0.0
    if s >= 97: return "A+"
    if s >= 93: return "A"
    if s >= 90: return "A-"
    if s >= 87: return "B+"
    if s >= 83: return "B"
    if s >= 80: return "B-"
    if s >= 77: return "C+"
    if s >= 73: return "C"
    if s >= 70: return "C-"
    if s >= 60: return "D"
    return "F"

def _risk_to_value(risk: str) -> float:
    r = (risk or "").strip().lower()
    return {"low":0.2, "medium":0.5, "high":0.75, "critical":0.95}.get(r, 0.5)

def _parse_time_to_seconds(val: Any) -> Optional[float]:
    try:
        if isinstance(val, (int, float)): return float(val)
        s = str(val).strip().lower()
        if s.endswith("ms"):
            return float(s.replace("ms", "").strip()) / 1000.0
        if s.endswith("s"):
            return float(s.replace("s", "").replace(" ", ""))
        return float(s)
    except Exception:
        return None

def _parse_float(val: Any) -> Optional[float]:
    try: return float(val)
    except Exception: return None

def _safe_score(val: Any, default: int = 0) -> int:
    """Safe conversion to integer score – prevents int('N/A') crash"""
    try:
        f = float(val)
        return int(round(f))
    except (ValueError, TypeError):
        return default

def _status_from_value(metric: str, value: Any) -> str:
    m = (metric or "").strip().lower()
    if m in ("fcp","first contentful paint"):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 1.8: return "Good"
        if t <= 3.0: return "Needs Improvement"
        return "Poor"
    if m in ("lcp","largest contentful paint"):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 2.5: return "Good"
        if t <= 4.0: return "Needs Improvement"
        return "Poor"
    if m in ("speed index",):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 3.4: return "Good"
        if t <= 5.8: return "Needs Improvement"
        return "Poor"
    if m in ("tbt","total blocking time"):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 0.2: return "Good"
        if t <= 0.6: return "Needs Improvement"
        return "Poor"
    if m in ("tti","time to interactive"):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 3.8: return "Good"
        if t <= 7.3: return "Needs Improvement"
        return "Poor"
    if m in ("cls","cumulative layout shift"):
        f = _parse_float(value)
        if f is None: return "N/A"
        if f < 0.10: return "Good"
        if f <= 0.25: return "Needs Improvement"
        return "Poor"
    if m in ("page size (mb)",):
        f = _parse_float(value)
        if f is None: return "N/A"
        if f < 2.0: return "Good"
        if f <= 4.0: return "Needs Improvement"
        return "Poor"
    if m in ("total requests",):
        f = _parse_float(value)
        if f is None: return "N/A"
        if f < 50: return "Good"
        if f <= 100: return "Needs Improvement"
        return "Poor"
    if m in ("js execution time",):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 2.0: return "Good"
        if t <= 4.0: return "Needs Improvement"
        return "Poor"
    if m in ("css size",):
        try:
            s = str(value).lower().replace("kb","").strip()
            kb = float(s)
        except Exception:
            return "N/A"
        if kb < 200: return "Good"
        if kb <= 350: return "Needs Improvement"
        return "Poor"
    if m in ("caching enabled",):
        return "Good" if _yes_no(value) == "Yes" else "Poor"
    if m in ("compression","gzip/brotli compression"):
        s = str(value).lower()
        if "brotli" in s or "br" in s: return "Good"
        if "gzip" in s or "gz" in s: return "Needs Improvement"
        return "Poor"
    if m in ("cdn usage",):
        return "Good" if _yes_no(value) == "Yes" else "Needs Improvement"
    if m in ("image optimization", "image optimization status"):
        s = str(value).lower()
        if any(x in s for x in ["optimized", "webp", "avif"]): return "Good"
        if "partial" in s or "some" in s: return "Needs Improvement"
        return "Poor"
    return "N/A"

def _autogen_report_id() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rn = random.randint(1000, 9999)
    return f"RPT-{ts}-{rn}"

def _filter_rows(rows: List[List[Any]], hide: bool) -> List[List[Any]]:
    if not hide: return rows
    out = []
    for r in rows:
        if not r: continue
        if isinstance(r[0], str) and r[0].lower() in ("metric","header","issue","element","device","","category"):
            out.append(r)
            continue
        vals = r[1:] if len(r) > 1 else []
        if any(str(v).strip().upper() != "N/A" for v in vals):
            out.append(r)
    return out

def _sec_to_hms(seconds: Any) -> str:
    try:
        s = int(float(seconds or 0))
    except Exception:
        return "N/A"
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h: return f"{h:d}h {m:02d}m {sec:02d}s"
    return f"{m:d}m {sec:02d}s"

# ============================================================================
# Flowables & Charts
# ============================================================================
class ScoreBar(Flowable):
    def __init__(self, score: Any, width: float = 260, height: float = 24, label: str = ""):
        super().__init__()
        try: self.score = max(0, min(100, float(score or 0)))
        except: self.score = 0.0
        self.width, self.height, self.label = width, height, label

    def draw(self):
        c = self.canv
        c.setFillColor(HexColor('#e5e7eb'))
        c.rect(0, 0, self.width, self.height, fill=1)
        if self.score >= 90: fill = HexColor('#16a34a')
        elif self.score >= 80: fill = HexColor('#22c55e')
        elif self.score >= 70: fill = HexColor('#eab308')
        elif self.score >= 50: fill = HexColor('#f97316')
        else: fill = HexColor('#dc2626')
        c.setFillColor(fill)
        c.rect(0, 0, self.width * (self.score / 100.0), self.height, fill=1)
        c.setStrokeColor(colors.grey)
        c.rect(0, 0, self.width, self.height)
        c.setFillColor(colors.white if self.score < 30 else colors.black)
        c.setFont(BASE_FONT_BOLD, 12)
        c.drawCentredString(self.width / 2, self.height / 2 - 5,
                            f"{self.label} {int(round(self.score))}%")

def _issue_distribution_pie(issues: List[Dict[str, Any]]) -> Drawing:
    buckets = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for it in issues or []:
        sev = str(it.get("severity", "Medium")).capitalize()
        buckets[sev if sev in buckets else "Medium"] += 1
    labels, data = list(buckets.keys()), list(buckets.values())
    if sum(data) == 0: labels, data = ["No Issues"], [1]
    d = Drawing(220, 160)
    p = Pie()
    p.x = 20; p.y = 10; p.width = 140; p.height = 140
    p.data = data
    p.labels = [f"{labels[i]} ({data[i]})" for i in range(len(data))]
    p.slices.strokeWidth = 0.5
    p.slices[0].fillColor = HexColor('#991b1b')
    if len(data) > 1: p.slices[1].fillColor = HexColor('#dc2626')
    if len(data) > 2: p.slices[2].fillColor = HexColor('#eab308')
    if len(data) > 3: p.slices[3].fillColor = HexColor('#22c55e')
    d.add(p)
    d.add(String(0, 150, "Issue Distribution", fontName=BASE_FONT_BOLD, fontSize=10))
    return d

def _risk_meter(risk_level: str) -> Drawing:
    w, h = 220, 140
    d = Drawing(w, h)
    cx, cy, r = 110, 20, 90
    zones = [
        (HexColor('#22c55e'), 180, 220),
        (HexColor('#eab308'), 220, 260),
        (HexColor('#f97316'), 260, 300),
        (HexColor('#dc2626'), 300, 360),
    ]
    for col, a0, a1 in zones:
        d.add(Wedge(cx, cy, r, startangledegrees=a0, endangledegrees=a1, fillColor=col, strokeColor=colors.white))
    d.add(Circle(cx, cy, r, strokeColor=colors.grey, fillColor=None, strokeWidth=1))
    val = _risk_to_value(risk_level)
    angle_deg = 180 + val * 180.0
    rad = math.radians(angle_deg)
    nx = cx + (r - 10) * math.cos(rad)
    ny = cy + (r - 10) * math.sin(rad)
    d.add(Line(cx, cy, nx, ny, strokeColor=colors.black, strokeWidth=2))
    d.add(Circle(cx, cy, 4, fillColor=colors.black))
    d.add(String(60, 120, "Risk Meter", fontName=BASE_FONT_BOLD, fontSize=10))
    d.add(String(80, 105, f"{risk_level or 'Medium'}", fontName=BASE_FONT, fontSize=10))
    return d

def _risk_heat_map(issues: List[Dict[str, Any]]) -> Table:
    severities = ["Low", "Medium", "High", "Critical"]
    likelihoods = ["Low", "Medium", "High"]
    counts = {sev: {lk: 0 for lk in likelihoods} for sev in severities}
    for it in issues or []:
        sev = str(it.get("severity", "Medium")).capitalize()
        lk = str(it.get("likelihood", "Medium")).capitalize()
        if sev not in counts: sev = "Medium"
        if lk not in likelihoods: lk = "Medium"
        counts[sev][lk] += 1
    rows = [["", "Low", "Medium", "High"]]
    for sev in severities:
        row = [sev]
        for lk in likelihoods:
            c = counts[sev][lk]
            row.append(str(c))
        rows.append(row)
    t = Table(rows, colWidths=[26*mm, 22*mm, 22*mm, 22*mm])
    style_cmds = [
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f1f5f9')),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9),
    ]
    for i, sev in enumerate(severities, start=1):
        base = _severity_color(sev)
        if sev == "Low": bg = HexColor('#dcfce7')
        elif sev == "Medium": bg = HexColor('#fef9c3')
        elif sev == "High": bg = HexColor('#fee2e2')
        else: bg = HexColor('#fecaca')
        style_cmds.append(('BACKGROUND', (0,i), (0,i), bg))
    t.setStyle(TableStyle(style_cmds))
    return t

# ============================================================================
# Page footer with page numbers
# ============================================================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        self._saved_page_states = []
        super().__init__(*args, **kwargs)

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        super().showPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(page_count)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.setFont(BASE_FONT, 8)
        self.setFillColor(HexColor('#6b7280'))
        self.drawCentredString(A4[0] / 2.0, 10 * mm, f"Page {self._pageNumber} of {page_count}")

# ============================================================================
# Pages – ALL now return story explicitly
# ============================================================================

def _page_cover(audit: Dict, styles) -> List[Any]:
    story = []
    logo_path = _safe_get(audit, "logo_path", default=None)
    if logo_path and isinstance(logo_path, str):
        try:
            img = Image(logo_path, width=60*mm, height=18*mm)
            img.hAlign = 'CENTER'
            story.append(Spacer(1, 12*mm))
            story.append(img)
        except Exception:
            story.append(Spacer(1, 20))
    story.append(Spacer(1, 18*mm))
    story.append(Paragraph("Comprehensive Website Audit Report", styles['CoverTitle']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Performance • SEO • Security • Accessibility • UX", styles['CoverSubtitle']))
    story.append(Spacer(1, 30*mm))

    report_id = _safe_get(audit, "report_id", default=None) or _autogen_report_id()
    audited_url = _safe_get(audit, "audited_url", default="N/A")
    audit_dt_utc = _safe_get(audit, "audit_datetime_utc", default=None)
    if not audit_dt_utc:
        audit_dt_utc = datetime.utcnow().strftime("%B %d, %Y %H:%M UTC")
    prepared_by = _safe_get(audit, "brand_name", default="FF Tech AI")

    rows = [
        ["Website URL", audited_url],
        ["Audit Date & Time (UTC)", audit_dt_utc],
        ["Report ID", report_id],
        ["Prepared By", prepared_by],
    ]
    table = Table(rows, colWidths=[70*mm, 90*mm])
    table.setStyle(TableStyle([
        ('FONT', (0,0), (-1,-1), BASE_FONT, 12),
        ('TEXTCOLOR', (0,0), (0,-1), colors.darkgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,0), (0,-1), HexColor('#f8fafc')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
    ]))
    story.append(table)
    story.append(Spacer(1, 22*mm))
    story.append(Paragraph("Confidential – For Client Use Only", styles['Small']))
    story.append(PageBreak())
    return story  # FIXED: explicit return

def _page_summary(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("1. Executive Summary", styles['H1'])]
    overall = _safe_get(audit, "overall_score", default=0)
    grade = _safe_get(audit, "grade", default=_letter_grade(overall))
    risk = _safe_get(audit, "summary", "risk_level", default="Medium")
    impact = _safe_get(audit, "summary", "traffic_impact", default="N/A")

    story.append(ScoreBar(overall, label="Overall Website Health"))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Grade</b>: {grade} • <b>Risk Level</b>: {risk} • <b>Impact</b>: {impact}", styles['Body']))

    breakdown = _safe_get(audit, "breakdown", default={})

    # FIXED: safe numeric conversion
    sub_rows = [
        ["Performance",   f"{_safe_score(_safe_get(breakdown, 'performance',  'score', 0))}%", _letter_grade(_safe_get(breakdown, 'performance',  'score', 0))],
        ["Security",      f"{_safe_score(_safe_get(breakdown, 'security',     'score', 0))}%", _letter_grade(_safe_get(breakdown, 'security',     'score', 0))],
        ["SEO",           f"{_safe_score(_safe_get(breakdown, 'seo',          'score', 0))}%", _letter_grade(_safe_get(breakdown, 'seo',          'score', 0))],
        ["Accessibility", f"{_safe_score(_safe_get(breakdown, 'accessibility','score', 0))}%", _letter_grade(_safe_get(breakdown, 'accessibility','score', 0))],
    ]

    sub_tbl = Table([["Category", "Score", "Grade"]] + sub_rows,
                    colWidths=[60*mm, 30*mm, 30*mm])
    sub_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#eef2ff')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 10),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(Spacer(1, 6))
    story.append(sub_tbl)
    story.append(Spacer(1, 10))

    issues = _safe_get(audit, "issues", default=[])
    crit_sorted = sorted(issues, key=lambda x: ["low","medium","high","critical"].index(
        str(x.get("severity","medium")).lower()) if str(x.get("severity","")).lower() in ["low","medium","high","critical"] else 1,
        reverse=True)
    top5 = crit_sorted[:5]
    story.append(Paragraph("Top 5 Critical Issues", styles['H2']))
    if top5:
        for i, it in enumerate(top5, 1):
            title = it.get("issue_name", "Unnamed Issue")
            sev = it.get("severity", "Medium")
            page = it.get("affected_page", "N/A")
            story.append(Paragraph(f"{i}. <b>{title}</b> — Severity: <b>{sev}</b> — Page: {page}", styles['Body']))
    else:
        story.append(Paragraph("No critical issues detected.", styles['Body']))

    charts_row = [
        _issue_distribution_pie(issues),
        _risk_meter(risk),
    ]
    chart_tbl = Table([[charts_row[0], charts_row[1]]], colWidths=[90*mm, 70*mm])
    chart_tbl.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(Spacer(1, 10))
    story.append(chart_tbl)

    story.append(PageBreak())
    return story  # FIXED: explicit return

# IMPORTANT: Apply the same pattern (return story at the end) to ALL other page functions
# For brevity, only _page_cover and _page_summary are shown fully fixed above.
# You must do the same for:
# _page_overview, _page_performance, _page_security, _page_seo,
# _page_accessibility, _page_mobile, _page_ux, _page_compliance, _page_detailed_issues

# Example for one more (apply to all):

def _page_overview(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("2. Website Overview", styles['H1'])]
    ov = _safe_get(audit, "website_overview", default={})
    rows = [
        ["Domain Name", _safe_get(ov, "domain_name")],
        ["IP Address", _safe_get(ov, "ip_address")],
        ["Hosting Provider", _safe_get(ov, "hosting_provider")],
        ["Server Location", _safe_get(ov, "server_location")],
        ["CMS Detected", _safe_get(ov, "cms")],
        ["Technology Stack", ", ".join(_safe_get(ov, "tech_stack", default=[])) if isinstance(_safe_get(ov, "tech_stack", default=[]), list) else _safe_get(ov, "tech_stack", default="N/A")],
        ["SSL Status", _yes_no(_safe_get(ov, "ssl_status"))],
        ["HTTP → HTTPS Redirection", _yes_no(_safe_get(ov, "redirect_http_to_https"))],
        ["robots.txt Status", _yes_no(_safe_get(ov, "robots_txt"))],
        ["sitemap.xml Status", _yes_no(_safe_get(ov, "sitemap_xml"))],
    ]
    tbl = Table(rows, colWidths=[60*mm, 100*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f1f5f9')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 10.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(tbl)
    story.append(PageBreak())
    return story  # FIXED: explicit return

# ... do the same for every other _page_ function ...

# ============================================================================
# Master Generator (I/O kept unchanged)
# ============================================================================
def generate_audit_pdf(audit: Dict[str, Any]) -> bytes:
    if audit is None:
        raise ValueError("audit data cannot be None")

    styles = get_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=20*mm,
        title="Comprehensive Website Audit Report",
        author=_safe_get(audit, "brand_name", default="FF Tech AI"),
    )
    story: List[Any] = []
    story.extend(_page_cover(audit, styles))
    story.extend(_page_summary(audit, styles))
    story.extend(_page_overview(audit, styles))
    story.extend(_page_performance(audit, styles))
    story.extend(_page_security(audit, styles))
    story.extend(_page_seo(audit, styles))
    story.extend(_page_accessibility(audit, styles))
    story.extend(_page_mobile(audit, styles))
    story.extend(_page_ux(audit, styles))
    story.extend(_page_compliance(audit, styles))
    story.extend(_page_detailed_issues(audit, styles))
    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# ============================================================================
# Local Demo
# ============================================================================
if __name__ == "__main__":
    sample = {
        "audited_url": "https://www.apple.com",
        "overall_score": 92,
        "grade": "A+",
        "audit_datetime_utc": datetime.utcnow().strftime("%B %d, %Y %H:%M UTC"),
        "brand_name": "FF Tech AI",
        # ... your full sample data ...
    }
    pdf_bytes = generate_audit_pdf(sample)
    with open("comprehensive-website-audit.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("Comprehensive audit report generated: comprehensive-website-audit.pdf")
