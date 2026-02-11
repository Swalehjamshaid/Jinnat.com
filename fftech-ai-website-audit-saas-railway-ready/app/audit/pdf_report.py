# -*- coding: utf-8 -*-
"""
fftech-ai-website-audit-saas-railway-ready/app/audit/pdf_report.py
World-class, comprehensive multi-page PDF Website Audit Report Generator
- Professional, client-ready with industry-standard metrics
- Includes: Cover, Executive Summary (with charts), Overview, Performance (CWV),
  Security (OWASP), SEO, Accessibility (WCAG 2.1), Mobile, UX/UI, Compliance, Issues
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
    PageBreak, Flowable, KeepInFrame, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Graphics (charts)
from reportlab.graphics.shapes import Drawing, String, Line, Circle, Wedge
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

# -------------------------------
# Font setup – better Unicode support
# -------------------------------
try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    BASE_FONT = "DejaVuSans"
except Exception:
    BASE_FONT = "Helvetica"


# -------------------------------
# Styles
# -------------------------------
def get_styles():
    s = getSampleStyleSheet()
    # Cover
    s.add(ParagraphStyle(name='CoverTitle', fontName=BASE_FONT, fontSize=28, alignment=TA_CENTER,
                         spaceAfter=40, textColor=HexColor('#1e40af')))
    s.add(ParagraphStyle(name='CoverSubtitle', fontName=BASE_FONT, fontSize=16,
                         alignment=TA_CENTER, textColor=colors.grey))
    # Headings
    s.add(ParagraphStyle(name='H1', fontName=BASE_FONT, fontSize=20,
                         spaceBefore=20, spaceAfter=12, textColor=HexColor('#1e3a8a')))
    s.add(ParagraphStyle(name='H2', fontName=BASE_FONT, fontSize=14,
                         spaceBefore=16, spaceAfter=8, textColor=HexColor('#0f172a')))
    s.add(ParagraphStyle(name='H3', fontName=BASE_FONT, fontSize=12.5,
                         spaceBefore=10, spaceAfter=6, textColor=HexColor('#0f172a')))
    # Body & small
    s.add(ParagraphStyle(name='Body', fontName=BASE_FONT, fontSize=10.5, leading=14))
    s.add(ParagraphStyle(name='Small', fontName=BASE_FONT, fontSize=9, textColor=colors.grey))
    s.add(ParagraphStyle(name='Footer', fontName=BASE_FONT, fontSize=8,
                         textColor=colors.grey, alignment=TA_CENTER))
    # Badges / inline emphasis
    s.add(ParagraphStyle(name='Badge', fontName=BASE_FONT, fontSize=9, textColor=colors.white,
                         backColor=HexColor('#475569'), leftIndent=4, rightIndent=4))
    s.add(ParagraphStyle(name='Mono', fontName=BASE_FONT, fontSize=9, leading=12,
                         textColor=HexColor('#0f172a')))
    return s


# -------------------------------
# Helpers & Utilities
# -------------------------------
def _safe_get(data: Dict, *keys: str, default: Any = "N/A") -> Any:
    cur = data
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k, {})
        else:
            return default
    return default if cur in (None, "", {}) else cur


def _yes_no(v: Any) -> str:
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if v in ("yes", "Yes", "Y", "y", 1, "true", "True"):
        return "Yes"
    if v in ("no", "No", "N", "n", 0, "false", "False"):
        return "No"
    return "N/A"


def _fmt(value: Any, suffix: str = "") -> str:
    if value in (None, "", {}, []):
        return "N/A"
    return f"{value}{suffix}"


def _letter_grade(score: Optional[float]) -> str:
    try:
        s = float(score or 0)
    except Exception:
        s = 0.0
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
    if r == "low": return 0.2
    if r == "medium": return 0.5
    if r == "high": return 0.75
    if r == "critical": return 0.95
    return 0.5


def _severity_color(sev: str):
    s = (sev or "").lower()
    if s == "critical": return HexColor('#991b1b')  # deep red
    if s == "high": return HexColor('#dc2626')      # red
    if s == "medium": return HexColor('#eab308')    # amber
    if s == "low": return HexColor('#22c55e')       # green
    return colors.grey


def _status_color(status: str):
    st = (status or "").lower()
    if st in ("good", "pass", "ok", "healthy"): return HexColor('#16a34a')
    if st in ("needs improvement", "medium", "warning"): return HexColor('#eab308')
    if st in ("poor", "fail", "critical", "high risk"): return HexColor('#dc2626')
    return colors.grey


def _autogen_report_id() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rn = random.randint(1000, 9999)
    return f"RPT-{ts}-{rn}"


def _ideal_values_map() -> Dict[str, Tuple[str, str]]:
    """
    Returns (ideal_value, impact_basis) for performance metrics.
    Values mostly follow Lighthouse/Web Vitals common thresholds.
    """
    return {
        "FCP": ("< 1.8s", "User-perceived load"),
        "LCP": ("< 2.5s", "Main content load"),
        "Speed Index": ("< 3.4s", "Visual load"),
        "TBT": ("< 200ms", "Interactivity delay"),
        "TTI": ("< 3.8s", "Interactive readiness"),
        "CLS": ("< 0.10", "Visual stability"),
        "Page Size (MB)": ("< 2.0", "Network efficiency"),
        "Total Requests": ("< 50", "Network overhead"),
        "JS Execution Time": ("< 2.0s", "Main thread"),
        "CSS Size": ("< 200KB", "Render blocking"),
        "Caching Enabled": ("Yes", "Repeat views"),
        "Compression": ("Brotli/GZIP", "Bandwidth"),
        "CDN Usage": ("Yes", "Edge performance"),
        "Image Optimization": ("Optimized", "Media performance"),
    }


def _status_from_value(metric: str, value: Any) -> str:
    """
    Heuristic: classify Good / Needs Improvement / Poor for key metrics.
    Accepts seconds (float) or strings like "1450 ms", "2.4s".
    """
    m = metric.lower()
    v = value

    def parse_time(val):
        try:
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip().lower()
            if s.endswith("ms"):
                return float(s.replace("ms", "").strip()) / 1000.0
            if s.endswith("s"):
                return float(s.replace("s", "").strip())
            return float(s)
        except Exception:
            return None

    def parse_float(val):
        try:
            return float(val)
        except Exception:
            return None

    if m in ("fcp", "first contentful paint"):
        t = parse_time(v)
        if t is None: return "N/A"
        if t < 1.8: return "Good"
        if t <= 3.0: return "Needs Improvement"
        return "Poor"

    if m in ("lcp", "largest contentful paint"):
        t = parse_time(v)
        if t is None: return "N/A"
        if t < 2.5: return "Good"
        if t <= 4.0: return "Needs Improvement"
        return "Poor"

    if m in ("speed index",):
        t = parse_time(v)
        if t is None: return "N/A"
        if t < 3.4: return "Good"
        if t <= 5.8: return "Needs Improvement"
        return "Poor"

    if m in ("tbt", "total blocking time"):
        t = parse_time(v)
        if t is None: return "N/A"
        if t < 0.2: return "Good"
        if t <= 0.6: return "Needs Improvement"
        return "Poor"

    if m in ("tti", "time to interactive"):
        t = parse_time(v)
        if t is None: return "N/A"
        if t < 3.8: return "Good"
        if t <= 7.3: return "Needs Improvement"
        return "Poor"

    if m in ("cls", "cumulative layout shift"):
        f = parse_float(v)
        if f is None: return "N/A"
        if f < 0.10: return "Good"
        if f <= 0.25: return "Needs Improvement"
        return "Poor"

    if m in ("page size (mb)",):
        f = parse_float(v)
        if f is None: return "N/A"
        if f < 2.0: return "Good"
        if f <= 4.0: return "Needs Improvement"
        return "Poor"

    if m in ("total requests",):
        f = parse_float(v)
        if f is None: return "N/A"
        if f < 50: return "Good"
        if f <= 100: return "Needs Improvement"
        return "Poor"

    if m in ("js execution time",):
        # value could be like "1450 ms" or "2.1s"
        t = parse_time(v)
        if t is None: return "N/A"
        if t < 2.0: return "Good"
        if t <= 4.0: return "Needs Improvement"
        return "Poor"

    if m in ("css size",):
        # accept "180KB" / number in KB
        try:
            s = str(v).lower().replace("kb", "").strip()
            kb = float(s)
        except Exception:
            return "N/A"
        if kb < 200: return "Good"
        if kb <= 350: return "Needs Improvement"
        return "Poor"

    if m in ("caching enabled",):
        return "Good" if _yes_no(v) == "Yes" else "Poor"

    if m in ("compression", "gzip/brotli compression"):
        s = str(v).lower()
        if "brotli" in s or "br" in s: return "Good"
        if "gzip" in s or "gz" in s: return "Needs Improvement"
        return "Poor"

    if m in ("cdn usage",):
        return "Good" if _yes_no(v) == "Yes" else "Needs Improvement"

    if m in ("image optimization", "image optimization status"):
        s = str(v).lower()
        if "optimized" in s or "webp" in s or "avif" in s: return "Good"
        if "partial" in s or "some" in s: return "Needs Improvement"
        return "Poor"

    return "N/A"


def _grade_row(label: str, score: Any) -> List[Any]:
    try:
        s = float(score or 0)
    except Exception:
        s = 0
    return [label, f"{int(round(s))}%", _letter_grade(s)]


# -------------------------------
# Visual Components (Flowables / Drawings)
# -------------------------------
class ScoreBar(Flowable):
    def __init__(self, score: Any, width: float = 240, height: float = 24, label: str = ""):
        super().__init__()
        try:
            self.score = max(0, min(100, float(score or 0)))
        except Exception:
            self.score = 0.0
        self.width = width
        self.height = height
        self.label = label

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(HexColor('#e5e7eb'))
        c.rect(0, 0, self.width, self.height, fill=1)
        # Fill
        if self.score >= 90:
            fill = HexColor('#16a34a')      # dark green
        elif self.score >= 80:
            fill = HexColor('#22c55e')      # green
        elif self.score >= 70:
            fill = HexColor('#eab308')      # yellow
        elif self.score >= 50:
            fill = HexColor('#f97316')      # orange
        else:
            fill = HexColor('#dc2626')      # red
        c.setFillColor(fill)
        c.rect(0, 0, self.width * (self.score / 100.0), self.height, fill=1)
        # Border
        c.setStrokeColor(colors.grey)
        c.rect(0, 0, self.width, self.height)
        # Text
        c.setFillColor(colors.white if self.score < 30 else colors.black)
        c.setFont(BASE_FONT, 12)
        c.drawCentredString(self.width / 2, self.height / 2 - 5,
                            f"{self.label} {int(round(self.score))}%")


def _issue_distribution_pie(issues: List[Dict[str, Any]]) -> Drawing:
    # Count by severity
    buckets = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for it in issues or []:
        sev = str(it.get("severity", "Medium")).capitalize()
        if sev not in buckets:
            sev = "Medium"
        buckets[sev] += 1

    labels = list(buckets.keys())
    data = list(buckets.values())
    if sum(data) == 0:
        labels = ["No Issues"]
        data = [1]

    d = Drawing(220, 160)
    p = Pie()
    p.x = 20
    p.y = 10
    p.width = 140
    p.height = 140
    p.data = data
    p.labels = [f"{labels[i]} ({data[i]})" for i in range(len(data))]
    p.slices.strokeWidth = 0.5
    p.slices[0].fillColor = HexColor('#991b1b')  # Critical
    if len(p.data) > 1: p.slices[1].fillColor = HexColor('#dc2626')  # High
    if len(p.data) > 2: p.slices[2].fillColor = HexColor('#eab308')  # Medium
    if len(p.data) > 3: p.slices[3].fillColor = HexColor('#22c55e')  # Low
    d.add(p)
    d.add(String(0, 150, "Issue Distribution", fontName=BASE_FONT, fontSize=10))
    return d


def _risk_meter(risk_level: str) -> Drawing:
    """
    Semi-circular risk meter with colored zones and a needle mapped to risk level.
    """
    w, h = 220, 140
    d = Drawing(w, h)
    cx, cy, r = 110, 20, 90
    # Zones (green -> yellow -> orange -> red)
    zones = [
        (HexColor('#22c55e'), 180, 220),
        (HexColor('#eab308'), 220, 260),
        (HexColor('#f97316'), 260, 300),
        (HexColor('#dc2626'), 300, 360),
    ]
    for col, a0, a1 in zones:
        d.add(Wedge(cx, cy, r, startangledegrees=a0, endangledegrees=a1, fillColor=col, strokeColor=colors.white))

    # Tick ring
    d.add(Circle(cx, cy, r, strokeColor=colors.grey, fillColor=None, strokeWidth=1))

    # Needle
    val = _risk_to_value(risk_level)  # 0..1 maps to 180..360
    angle_deg = 180 + val * 180.0
    rad = math.radians(angle_deg)
    nx = cx + (r - 10) * math.cos(rad)
    ny = cy + (r - 10) * math.sin(rad)
    d.add(Line(cx, cy, nx, ny, strokeColor=colors.black, strokeWidth=2))
    d.add(Circle(cx, cy, 4, fillColor=colors.black))

    # Label
    d.add(String(60, 120, "Risk Meter", fontName=BASE_FONT, fontSize=10))
    d.add(String(80, 105, f"{risk_level or 'Medium'}", fontName=BASE_FONT, fontSize=10))
    return d


def _risk_heat_map(issues: List[Dict[str, Any]]) -> Table:
    """
    Simple heat map by Severity vs Likelihood (if missing, assume Medium).
    """
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
    # Color map by severity on rows
    style_cmds = [
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f1f5f9')),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9),
    ]
    for i, sev in enumerate(severities, start=1):
        base = _severity_color(sev)
        # Slightly transparent backgrounds simulated with lighter tones
        if sev == "Low": bg = HexColor('#dcfce7')
        elif sev == "Medium": bg = HexColor('#fef9c3')
        elif sev == "High": bg = HexColor('#fee2e2')
        else: bg = HexColor('#fecaca')
        style_cmds.append(('BACKGROUND', (0,i), (0,i), bg))
    t.setStyle(TableStyle(style_cmds))
    return t


# -------------------------------
# Pages
# -------------------------------
def _page_cover(audit: Dict, styles) -> List[Any]:
    story = []
    # Optional logo
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

    # Metadata rows
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
    return story


def _page_summary(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("1. Executive Summary", styles['H1'])]

    overall = _safe_get(audit, "overall_score", default=0)
    grade = _safe_get(audit, "grade", default=_letter_grade(overall))
    risk = _safe_get(audit, "summary", "risk_level", default="Medium")
    impact = _safe_get(audit, "summary", "traffic_impact", default="N/A")

    story.append(ScoreBar(overall, label="Overall Website Health"))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Grade</b>: {grade}  •  <b>Risk Level</b>: {risk}  •  <b>Impact</b>: {impact}", styles['Body']))

    # Sub-scores
    breakdown = _safe_get(audit, "breakdown", default={})
    sub_rows = [
        _grade_row("Performance", _safe_get(breakdown, "performance", "score", default=0)),
        _grade_row("Security", _safe_get(breakdown, "security", "score", default=0)),
        _grade_row("SEO", _safe_get(breakdown, "seo", "score", default=0)),
        _grade_row("Accessibility", _safe_get(breakdown, "accessibility", "score", default=0)),
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

    # Top 5 Critical Issues
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

    # Visuals: Pie + Risk Meter
    charts_row = [
        _issue_distribution_pie(issues),
        _risk_meter(risk),
    ]
    chart_tbl = Table([[charts_row[0], charts_row[1]]], colWidths=[90*mm, 70*mm])
    chart_tbl.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(Spacer(1, 10))
    story.append(chart_tbl)
    story.append(PageBreak())
    return story


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
    return story


def _page_performance(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("3. Performance Audit (Core Web Vitals)", styles['H1'])]

    # Merge sources: breakdown.performance.extras and audit.core_web_vitals
    extras = {}
    extras.update(_safe_get(audit, "core_web_vitals", default={}) or {})
    extras.update(_safe_get(audit, "breakdown", "performance", "extras", default={}) or {})

    # Build metrics rows
    ideal_map = _ideal_values_map()
    metrics_display = [
        ("FCP", extras.get("fcp") or extras.get("first_contentful_paint") or extras.get("load_ms")),
        ("LCP", extras.get("lcp")),
        ("Speed Index", extras.get("speed_index")),
        ("TBT", extras.get("tbt") or extras.get("total_blocking_time")),
        ("TTI", extras.get("tti") or extras.get("time_to_interactive")),
        ("CLS", extras.get("cls") or extras.get("cumulative_layout_shift")),
        ("Page Size (MB)", extras.get("page_size_mb") or (extras.get("bytes") and round(float(extras.get("bytes", 0))/1024/1024, 2))),
        ("Total Requests", extras.get("total_requests")),
        ("JS Execution Time", extras.get("js_execution_time") or extras.get("scripts") and f"{extras.get('scripts')} scripts"),
        ("CSS Size", extras.get("css_size_kb")),
        ("Image Optimization", extras.get("image_optimization_status") or extras.get("image_formats")),
        ("Caching Enabled", extras.get("caching_enabled")),
        ("Compression", extras.get("compression") or ("Brotli" if extras.get("brotli") else "GZIP" if extras.get("gzip") else "None")),
        ("CDN Usage", extras.get("cdn") or extras.get("cdn_usage")),
    ]

    rows = [["Metric", "Value", "Ideal Value", "Status", "Impact"]]
    for metric, val in metrics_display:
        ideal, impact = ideal_map.get(metric, ("N/A", "N/A"))
        status = _status_from_value(metric, val)
        rows.append([metric, _fmt(val), ideal, status, impact])

    tbl = Table(rows, colWidths=[42*mm, 32*mm, 34*mm, 26*mm, 36*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f0fdf4')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(tbl)

    perf_score = _safe_get(audit, "breakdown", "performance", "score", default=0)
    story.append(Spacer(1, 8))
    story.append(ScoreBar(perf_score, label="Performance Score"))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Improvement Recommendations", styles['H2']))
    actions = _safe_get(audit, "priority_actions", default=[])
    if actions:
        for a in actions:
            if any(k in str(a).lower() for k in ["image", "lazy", "webp", "avif", "minify", "cache", "gzip", "brotli", "cdn", "render"]):
                story.append(Paragraph(f"• {a}", styles['Body']))
    else:
        story.append(Paragraph("• Optimize images with next-gen formats and lazy loading", styles['Body']))
        story.append(Paragraph("• Minify and compress JS/CSS/HTML; enable Brotli", styles['Body']))
        story.append(Paragraph("• Reduce render-blocking resources; leverage caching/CDN", styles['Body']))
    story.append(PageBreak())
    return story


def _page_security(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("4. Security Audit (OWASP Based)", styles['H1'])]

    sec = _safe_get(audit, "security_details", default={})
    # SSL & Encryption
    ssl_rows = [
        ["SSL & Encryption", _yes_no(_safe_get(sec, "ssl_enabled"))],
        ["SSL Validity", _yes_no(_safe_get(sec, "ssl_valid"))],
        ["Certificate Expiry", _safe_get(sec, "cert_expiry", default="N/A")],
        ["TLS Version", _safe_get(sec, "tls_version", default="N/A")],
        ["Mixed Content", _yes_no(_safe_get(sec, "mixed_content"))],
    ]
    ssl_tbl = Table(ssl_rows, colWidths=[60*mm, 100*mm])
    ssl_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f8fafc')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 10),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(Paragraph("SSL & Encryption", styles['H2']))
    story.append(ssl_tbl)
    story.append(Spacer(1, 8))

    # Security Headers
    hdrs = [
        ("Content-Security-Policy", _safe_get(sec, "headers", "content_security_policy", default=False)),
        ("X-Frame-Options", _safe_get(sec, "headers", "x_frame_options", default=False)),
        ("X-Content-Type-Options", _safe_get(sec, "headers", "x_content_type_options", default=False)),
        ("Strict-Transport-Security", _safe_get(sec, "headers", "strict_transport_security", default=False)),
        ("Referrer-Policy", _safe_get(sec, "headers", "referrer_policy", default=False)),
        ("Permissions-Policy", _safe_get(sec, "headers", "permissions_policy", default=False)),
    ]
    hdr_rows = [["Header", "Present"]]
    for n, v in hdrs:
        hdr_rows.append([n, _yes_no(v)])
    hdr_tbl = Table(hdr_rows, colWidths=[80*mm, 30*mm])
    hdr_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#fff7ed')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(Paragraph("Security Headers", styles['H2']))
    story.append(hdr_tbl)
    story.append(Spacer(1, 8))

    # Vulnerability Checks
    vuln_rows = [
        ["SQL Injection Risk", _yes_no(_safe_get(sec, "vulnerabilities", "sql_injection"))],
        ["XSS Risk", _yes_no(_safe_get(sec, "vulnerabilities", "xss"))],
        ["CSRF Protection", _yes_no(_safe_get(sec, "vulnerabilities", "csrf_protection"))],
        ["Open Ports", ", ".join(map(str, _safe_get(sec, "vulnerabilities", "open_ports", default=[]) or [])) or "N/A"],
        ["Directory Listing Enabled", _yes_no(_safe_get(sec, "vulnerabilities", "directory_listing"))],
        ["Admin Panel Exposure", _yes_no(_safe_get(sec, "vulnerabilities", "admin_panel_exposed"))],
        ["Outdated Libraries", ", ".join(_safe_get(sec, "vulnerabilities", "outdated_libraries", default=[]) or ["N/A"])],
    ]
    vuln_tbl = Table(vuln_rows, colWidths=[70*mm, 90*mm])
    vuln_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#fee2e2')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(Paragraph("Vulnerability Checks", styles['H2']))
    story.append(vuln_tbl)
    story.append(Spacer(1, 10))

    # Security Score Table
    sec_rows = [["Issue", "Severity", "Status", "Recommendation"]]
    # Try to source items from issues list with category "Security"
    issues = _safe_get(audit, "issues", default=[])
    sec_issues = [it for it in (issues or []) if str(it.get("category","")).lower() == "security"]
    if not sec_issues:
        sec_rows += [
            ["Missing CSP", "High", "Open", "Define a strict Content-Security-Policy"],
            ["X-Frame-Options absent", "Medium", "Open", "Add 'SAMEORIGIN' or 'DENY'"],
        ]
    else:
        for it in sec_issues[:8]:
            sec_rows.append([
                it.get("issue_name", "Security Issue"),
                it.get("severity", "Medium"),
                it.get("status", "Open"),
                it.get("recommendation", "Fix as per OWASP best practices"),
            ])
    s_tbl = Table(sec_rows, colWidths=[54*mm, 22*mm, 22*mm, 62*mm])
    s_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#fef2f2')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.3),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(Paragraph("Security Score Table", styles['H2']))
    story.append(s_tbl)
    story.append(Spacer(1, 8))

    # Risk Heat Map
    story.append(Paragraph("Risk Heat Map", styles['H2']))
    story.append(_risk_heat_map(issues))
    story.append(PageBreak())
    return story


def _page_seo(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("5. SEO Audit (Technical + On Page)", styles['H1'])]

    seo = _safe_get(audit, "seo_details", default={})
    # Technical SEO
    tech_rows = [
        ["Meta Title Length", _fmt(_safe_get(seo, "meta_title_length"))],
        ["Meta Description Length", _fmt(_safe_get(seo, "meta_description_length"))],
        ["H1–H6 Structure", _fmt(_safe_get(seo, "heading_structure"))],
        ["Canonical Tag", _fmt(_safe_get(seo, "canonical_tag"))],
        ["Schema Markup", _fmt(_safe_get(seo, "schema_markup"))],
        ["Robots.txt", _yes_no(_safe_get(seo, "robots_txt"))],
        ["Sitemap", _yes_no(_safe_get(seo, "sitemap"))],
        ["Broken Links", _fmt(_safe_get(seo, "broken_links"))],
        ["Redirect Chains", _fmt(_safe_get(seo, "redirect_chains"))],
        ["404 Errors", _fmt(_safe_get(seo, "errors_404"))],
        ["URL Structure", _fmt(_safe_get(seo, "url_structure"))],
        ["Mobile Friendliness", _fmt(_safe_get(seo, "mobile_friendliness"))],
    ]
    story.append(Paragraph("Technical SEO", styles['H2']))
    tech_tbl = Table(tech_rows, colWidths=[70*mm, 80*mm])
    tech_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f8fafc')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(tech_tbl)
    story.append(Spacer(1, 8))

    # On-Page SEO
    onp_rows = [
        ["Keyword Density", _fmt(_safe_get(seo, "keyword_density"))],
        ["Alt Tags on Images", _fmt(_safe_get(seo, "alt_tags"))],
        ["Internal Linking", _fmt(_safe_get(seo, "internal_linking"))],
        ["Page Depth", _fmt(_safe_get(seo, "page_depth"))],
        ["Anchor Text Optimization", _fmt(_safe_get(seo, "anchor_text_optimization"))],
    ]
    story.append(Paragraph("On-Page SEO", styles['H2']))
    onp_tbl = Table(onp_rows, colWidths=[70*mm, 80*mm])
    onp_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#fff7ed')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(onp_tbl)
    story.append(Spacer(1, 8))

    # Consolidated Score Table
    score = _safe_get(audit, "breakdown", "seo", "score", default=0)
    rows = [["Element", "Status", "Impact", "Fix Required"]]
    # Attempt to derive a few structured items
    rows += [
        ["Meta Title", "Present" if _safe_get(audit, "breakdown", "seo", "extras", "title", default="") else "Missing",
         "High", "Add unique, 50–60 chars"],
        ["Meta Description", "Present" if _safe_get(audit, "breakdown", "seo", "extras", "meta_description_present", default=False) else "Missing",
         "Medium", "Add 140–160 chars"],
        ["Headers", _fmt(_safe_get(audit, "breakdown", "seo", "extras", "h1_count"), " H1 found"),
         "Medium", "One H1; structured H2-H3"],
    ]
    tbl = Table(rows, colWidths=[50*mm, 30*mm, 20*mm, 50*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#ecfeff')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(Paragraph(f"SEO Score: {int(round(float(score or 0)))}%", styles['H2']))
    story.append(tbl)
    story.append(PageBreak())
    return story


def _page_accessibility(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("6. Accessibility Audit (WCAG 2.1)", styles['H1'])]

    acc = _safe_get(audit, "accessibility_details", default={})
    rows = [
        ["Alt Text for Images", _yes_no(_safe_get(acc, "alt_text"))],
        ["Color Contrast Ratio", _fmt(_safe_get(acc, "color_contrast_ratio"))],
        ["ARIA Labels", _yes_no(_safe_get(acc, "aria_labels"))],
        ["Keyboard Navigation", _yes_no(_safe_get(acc, "keyboard_navigation"))],
        ["Form Labels", _yes_no(_safe_get(acc, "form_labels"))],
        ["Focus Indicators", _yes_no(_safe_get(acc, "focus_indicators"))],
        ["Heading Structure", _fmt(_safe_get(acc, "heading_structure"))],
        ["Skip Navigation Links", _yes_no(_safe_get(acc, "skip_links"))],
    ]
    tbl = Table(rows, colWidths=[70*mm, 80*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f0f9ff')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(tbl)
    score = _safe_get(audit, "breakdown", "accessibility", "score", default=0)
    compliance = _safe_get(acc, "compliance_level", default="N/A")
    story.append(Spacer(1, 8))
    story.append(ScoreBar(score, label=f"Accessibility Score — Compliance: {compliance}"))
    story.append(PageBreak())
    return story


def _page_mobile(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("7. Mobile Responsiveness Audit", styles['H1'])]

    mob = _safe_get(audit, "mobile_details", default={})
    rows = [
        ["Viewport Meta Tag", _yes_no(_safe_get(mob, "viewport_meta_tag"))],
        ["Responsive Layout", _yes_no(_safe_get(mob, "responsive_layout"))],
        ["Tap Target Size", _fmt(_safe_get(mob, "tap_target_size"))],
        ["Font Size Readability", _fmt(_safe_get(mob, "font_readability"))],
        ["Mobile Speed Score", _fmt(_safe_get(mob, "mobile_speed_score"))],
        ["Mobile Usability Issues", _fmt(_safe_get(mob, "usability_issues"))],
    ]
    tbl = Table(rows, colWidths=[70*mm, 80*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f0fdf4')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))

    # Device Compatibility Table
    comp = _safe_get(mob, "device_compatibility", default={})
    dev_rows = [["Device", "Compatibility"]]
    dev_rows += [
        ["Mobile", _yes_no(_safe_get(comp, "mobile"))],
        ["Tablet", _yes_no(_safe_get(comp, "tablet"))],
        ["Desktop", _yes_no(_safe_get(comp, "desktop"))],
    ]
    dev_tbl = Table(dev_rows, colWidths=[40*mm, 30*mm])
    dev_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#ecfeff')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(Paragraph("Device Compatibility", styles['H2']))
    story.append(dev_tbl)
    story.append(PageBreak())
    return story


def _page_ux(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("8. UX / UI Audit (Nielsen Heuristics)", styles['H1'])]

    ux = _safe_get(audit, "ux_details", default={})
    rows = [
        ["Navigation Clarity", _fmt(_safe_get(ux, "navigation_clarity"))],
        ["CTA Visibility", _fmt(_safe_get(ux, "cta_visibility"))],
        ["Page Load Feedback", _fmt(_safe_get(ux, "page_load_feedback"))],
        ["Error Messaging", _fmt(_safe_get(ux, "error_messaging"))],
        ["Form Simplicity", _fmt(_safe_get(ux, "form_simplicity"))],
        ["Visual Hierarchy", _fmt(_safe_get(ux, "visual_hierarchy"))],
        ["Trust Signals", _fmt(_safe_get(ux, "trust_signals"))],
        ["Consistency", _fmt(_safe_get(ux, "consistency"))],
    ]
    tbl = Table(rows, colWidths=[70*mm, 80*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#f8fafc')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(tbl)
    ux_score = _safe_get(ux, "score", default=_safe_get(audit, "breakdown", "links", "score", default=0))
    story.append(Spacer(1, 8))
    story.append(ScoreBar(ux_score, label="UX Score"))
    story.append(PageBreak())
    return story


def _page_compliance(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("9. Compliance & Privacy", styles['H1'])]

    cp = _safe_get(audit, "compliance_privacy", default={})
    rows = [
        ["GDPR Cookie Consent", _yes_no(_safe_get(cp, "gdpr_cookie_consent"))],
        ["Privacy Policy Page", _yes_no(_safe_get(cp, "privacy_policy"))],
        ["Terms & Conditions", _yes_no(_safe_get(cp, "terms_conditions"))],
        ["Cookie Banner", _yes_no(_safe_get(cp, "cookie_banner"))],
        ["Data Collection Transparency", _yes_no(_safe_get(cp, "data_collection_transparency"))],
        ["Third-Party Tracking Scripts", _fmt(_safe_get(cp, "third_party_tracking"))],
    ]
    tbl = Table(rows, colWidths=[70*mm, 80*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#fff7ed')),
        ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
        ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
    ]))
    story.append(tbl)
    story.append(PageBreak())
    return story


def _page_detailed_issues(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("10. Detailed Issue Breakdown", styles['H1'])]

    issues = _safe_get(audit, "issues", default=[])
    if not issues:
        story.append(Paragraph("No issues were provided for breakdown.", styles['Body']))
        return story

    for idx, it in enumerate(issues, start=1):
        story.append(Paragraph(f"Issue {idx}: {it.get('issue_name','Issue')}", styles['H2']))
        rows = [
            ["Category", _fmt(it.get("category"))],
            ["Severity", _fmt(it.get("severity"))],
            ["Status", _fmt(it.get("status", "Open"))],
            ["Affected Page", _fmt(it.get("affected_page"))],
            ["Technical Explanation", _fmt(it.get("technical_explanation"))],
            ["Impact", _fmt(it.get("impact"))],
            ["Estimated Fix Time", _fmt(it.get("estimated_fix_time"))],
        ]
        tbl = Table(rows, colWidths=[40*mm, 110*mm])
        tbl.setStyle(TableStyle([
            ('FONT', (0,0), (-1,-1), BASE_FONT, 9.5),
            ('GRID', (0,0), (-1,-1), 0.4, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), HexColor('#f8fafc')),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6))

        # Optional screenshot
        screenshot_path = it.get("screenshot_path")
        if screenshot_path:
            try:
                img = Image(screenshot_path, width=140*mm, height=70*mm)
                story.append(Spacer(1, 4))
                story.append(img)
                story.append(Spacer(1, 4))
            except Exception:
                story.append(Paragraph("Screenshot could not be loaded.", styles['Small']))

        # Optional code example
        code = it.get("fix_code_example")
        if code:
            story.append(Paragraph("Fix Code Example:", styles['H3']))
            # render as monospaced paragraph (keeping base font for Unicode)
            story.append(Paragraph(f"<font name='{BASE_FONT}' size='9'><br/>{code}</font>", styles['Mono']))

        story.append(Spacer(1, 10))
    return story


# -------------------------------
# Master Generator (I/O kept unchanged)
# -------------------------------
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

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# -------------------------------
# Local Demo (kept intact; still produces a PDF if executed directly)
# -------------------------------
if __name__ == "__main__":
    sample = {
        "logo_path": "",  # optional: path to logo image
        "audited_url": "https://www.apple.com",
        "overall_score": 92,
        "grade": "A+",
        "audit_datetime": "February 10, 2026",
        "audit_datetime_utc": datetime.utcnow().strftime("%B %d, %Y %H:%M UTC"),
        "brand_name": "FF Tech AI",
        "website_overview": {
            "domain_name": "apple.com",
            "ip_address": "17.253.144.10",
            "hosting_provider": "Apple",
            "server_location": "US",
            "cms": "Custom",
            "tech_stack": ["React", "Node", "CDN"],
            "ssl_status": True,
            "redirect_http_to_https": True,
            "robots_txt": True,
            "sitemap_xml": True,
        },
        "breakdown": {
            "performance": {"score": 88, "extras": {"load_ms": "1450 ms", "bytes": 980000, "scripts": 18, "styles": 6}},
            "seo": {"score": 95, "extras": {"title": "Apple - Official Site", "meta_description_present": True,
                                             "canonical": "https://www.apple.com/", "h1_count": 1,
                                             "images_total": 12, "images_missing_alt": 0}},
            "security": {"score": 92, "https": True, "hsts": True, "status_code": 200, "server": "Apple CDN"},
            "links": {"score": 90},
            "accessibility": {"score": 88}
        },
        "core_web_vitals": {
            "fcp": "1.2s",
            "lcp": "2.1s",
            "speed_index": "2.9s",
            "tbt": "120ms",
            "tti": "3.1s",
            "cls": 0.05,
            "page_size_mb": 1.8,
            "total_requests": 48,
            "js_execution_time": "1.8s",
            "css_size_kb": 180,
            "image_optimization_status": "Optimized (WebP/AVIF)",
            "caching_enabled": True,
            "compression": "Brotli",
            "cdn": True
        },
        "security_details": {
            "ssl_enabled": True,
            "ssl_valid": True,
            "cert_expiry": "2026-12-01",
            "tls_version": "TLS 1.3",
            "mixed_content": False,
            "headers": {
                "content_security_policy": True,
                "x_frame_options": True,
                "x_content_type_options": True,
                "strict_transport_security": True,
                "referrer_policy": True,
                "permissions_policy": True
            },
            "vulnerabilities": {
                "sql_injection": False,
                "xss": False,
                "csrf_protection": True,
                "open_ports": [80, 443],
                "directory_listing": False,
                "admin_panel_exposed": False,
                "outdated_libraries": []
            }
        },
        "seo_details": {
            "meta_title_length": 18,
            "meta_description_length": 150,
            "heading_structure": "H1 present, H2/H3 structured",
            "canonical_tag": "Present",
            "schema_markup": "Organization, WebSite",
            "robots_txt": True,
            "sitemap": True,
            "broken_links": 0,
            "redirect_chains": 0,
            "errors_404": 0,
            "url_structure": "Clean",
            "mobile_friendliness": "Mobile-friendly",
            "keyword_density": "Balanced",
            "alt_tags": "OK",
            "internal_linking": "Healthy",
            "page_depth": "≤ 3 clicks",
            "anchor_text_optimization": "Good"
        },
        "accessibility_details": {
            "alt_text": True,
            "color_contrast_ratio": "≥ 4.5:1",
            "aria_labels": True,
            "keyboard_navigation": True,
            "form_labels": True,
            "focus_indicators": True,
            "heading_structure": "Semantic",
            "skip_links": True,
            "compliance_level": "AA"
        },
        "mobile_details": {
            "viewport_meta_tag": True,
            "responsive_layout": True,
            "tap_target_size": "Adequate",
            "font_readability": "Good",
            "mobile_speed_score": "85/100",
            "usability_issues": "None",
            "device_compatibility": {"mobile": True, "tablet": True, "desktop": True}
        },
        "ux_details": {
            "navigation_clarity": "Clear",
            "cta_visibility": "Prominent",
            "page_load_feedback": "Visible",
            "error_messaging": "Helpful",
            "form_simplicity": "Simple",
            "visual_hierarchy": "Strong",
            "trust_signals": "Visible",
            "consistency": "Consistent",
            "score": 90
        },
        "compliance_privacy": {
            "gdpr_cookie_consent": True,
            "privacy_policy": True,
            "terms_conditions": True,
            "cookie_banner": True,
            "data_collection_transparency": True,
            "third_party_tracking": "Analytics, Ads"
        },
        "dynamic": {},
        "summary": {"risk_level": "Low", "traffic_impact": "Good performance detected"},
        "priority_actions": [
            "Optimize hero images with AVIF/WebP format",
            "Minify JS/CSS/HTML and reduce total requests",
            "Enable Strict-Transport-Security (HSTS)",
            "Improve color contrast on buttons/CTAs",
        ],
        "issues": [
            {
                "issue_name": "Missing Content-Security-Policy",
                "category": "Security",
                "severity": "High",
                "status": "Open",
                "affected_page": "/",
                "technical_explanation": "CSP header absent; risk of XSS via injected scripts.",
                "impact": "High risk of client-side injection",
                "fix_code_example": "Content-Security-Policy: default-src 'self'; script-src 'self' cdn.example.com;",
                "estimated_fix_time": "2–4 hours",
                "likelihood": "High"
            },
            {
                "issue_name": "Large LCP due to hero image",
                "category": "Performance",
                "severity": "Medium",
                "status": "Open",
                "affected_page": "/home",
                "technical_explanation": "Hero image not lazy-loaded; not compressed with AVIF/WebP.",
                "impact": "Slower main content load",
                "fix_code_example": "<img src='hero.avif' loading='lazy' width='...' height='...'/>",
                "estimated_fix_time": "1–2 hours",
                "likelihood": "Medium"
            }
        ]
    }

    pdf_bytes = generate_audit_pdf(sample)
    with open("comprehensive-website-audit.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("Comprehensive audit report generated: comprehensive-website-audit.pdf")
