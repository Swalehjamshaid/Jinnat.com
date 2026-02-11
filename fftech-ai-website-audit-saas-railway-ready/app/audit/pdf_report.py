# -*- coding: utf-8 -*-
"""
fftech-ai-website-audit-saas-railway-ready/app/audit/pdf_report.py

Comprehensive, graph-rich Website Audit PDF Generator
- Keeps I/O identical: generate_audit_pdf(audit: Dict[str, Any]) -> bytes
- Sharper fonts (Noto/DejaVu fallback), high-contrast colors
- Page numbers (Page X of Y)
- Visuals across sections: pies, donuts, grouped bars, coverage bars, heat map
- Competitor Comparison: apple-to-apple table + grouped bar charts (scores & CWV)
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
from reportlab.lib.enums import TA_CENTER
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
                         spaceAfter=28, textColor=HexColor('#1e293b')))  # slate-800
    s.add(ParagraphStyle(name='CoverSubtitle', fontName=BASE_FONT, fontSize=14, alignment=TA_CENTER,
                         textColor=HexColor('#475569')))  # slate-600
    # Headings
    s.add(ParagraphStyle(name='H1', fontName=BASE_FONT_BOLD, fontSize=20, spaceBefore=14, spaceAfter=10,
                         textColor=HexColor('#0f172a')))  # slate-900
    s.add(ParagraphStyle(name='H2', fontName=BASE_FONT_BOLD, fontSize=13.5, spaceBefore=10, spaceAfter=6,
                         textColor=HexColor('#0f172a')))
    s.add(ParagraphStyle(name='H3', fontName=BASE_FONT_BOLD, fontSize=12, spaceBefore=8, spaceAfter=4))
    # Body
    s.add(ParagraphStyle(name='Body', fontName=BASE_FONT, fontSize=11, leading=15, textColor=HexColor('#111827')))
    s.add(ParagraphStyle(name='Small', fontName=BASE_FONT, fontSize=9, textColor=HexColor('#64748b'), leading=12))
    s.add(ParagraphStyle(name='Footer', fontName=BASE_FONT, fontSize=8, textColor=HexColor('#6b7280'), alignment=TA_CENTER))
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
    if s in ("yes", "y", "true", "1"): return "Yes"
    if s in ("no", "n", "false", "0"): return "No"
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
    return {"low": 0.2, "medium": 0.5, "high": 0.75, "critical": 0.95}.get(r, 0.5)


def _parse_time_to_seconds(val: Any) -> Optional[float]:
    """Accepts floats, '120 ms', '1.8 s', '1.8s', '120ms'… Returns seconds."""
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


def _status_from_value(metric: str, value: Any) -> str:
    """
    Heuristic Good / Needs Improvement / Poor classifier for common metrics.
    """
    m = (metric or "").strip().lower()

    if m in ("fcp", "first contentful paint"):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 1.8: return "Good"
        if t <= 3.0: return "Needs Improvement"
        return "Poor"

    if m in ("lcp", "largest contentful paint"):
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

    if m in ("tbt", "total blocking time"):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 0.2: return "Good"
        if t <= 0.6: return "Needs Improvement"
        return "Poor"

    if m in ("tti", "time to interactive"):
        t = _parse_time_to_seconds(value)
        if t is None: return "N/A"
        if t < 3.8: return "Good"
        if t <= 7.3: return "Needs Improvement"
        return "Poor"

    if m in ("cls", "cumulative layout shift"):
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
            s = str(value).lower().replace("kb", "").strip()
            kb = float(s)
        except Exception:
            return "N/A"
        if kb < 200: return "Good"
        if kb <= 350: return "Needs Improvement"
        return "Poor"

    if m in ("caching enabled",):
        return "Good" if _yes_no(value) == "Yes" else "Poor"

    if m in ("compression", "gzip/brotli compression"):
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
    """
    Optionally remove rows whose value column is 'N/A'. Assumes 2+ column rows.
    Header rows (first cell is 'Metric'/'Header'/etc.) are retained.
    """
    if not hide: return rows
    out = []
    for r in rows:
        if not r: continue
        if isinstance(r[0], str) and r[0].lower() in (
            "metric", "header", "issue", "element", "device", "", "category"
        ):
            out.append(r); continue
        vals = r[1:] if len(r) > 1 else []
        if any(str(v).strip().upper() != "N/A" for v in vals):
            out.append(r)
    return out


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
        c.setFillColor(HexColor('#e5e7eb')); c.rect(0, 0, self.width, self.height, fill=1)
        if self.score >= 90: fill = HexColor('#16a34a')
        elif self.score >= 80: fill = HexColor('#22c55e')
        elif self.score >= 70: fill = HexColor('#eab308')
        elif self.score >= 50: fill = HexColor('#f97316')
        else: fill = HexColor('#dc2626')
        c.setFillColor(fill); c.rect(0, 0, self.width * (self.score / 100.0), self.height, fill=1)
        c.setStrokeColor(colors.grey); c.rect(0, 0, self.width, self.height)
        c.setFillColor(colors.white if self.score < 30 else colors.black)
        c.setFont(BASE_FONT_BOLD, 12)
        c.drawCentredString(self.width / 2, self.height / 2 - 5, f"{self.label} {int(round(self.score))}%")


def _issue_distribution_pie(issues: List[Dict[str, Any]]) -> Drawing:
    buckets = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for it in issues or []:
        sev = str(it.get("severity", "Medium")).capitalize()
        buckets[sev if sev in buckets else "Medium"] += 1
    labels, data = list(buckets.keys()), list(buckets.values())
    if sum(data) == 0: labels, data = ["No Issues"], [1]
    d = Drawing(220, 160)
    p = Pie(); p.x = 20; p.y = 10; p.width = 140; p.height = 140
    p.data = data
    p.labels = [f"{labels[i]} ({data[i]})" for i in range(len(data))]
    p.slices.strokeWidth = 0.5
    p.slices[0].fillColor = HexColor('#991b1b')
    if len(data) > 1: p.slices[1].fillColor = HexColor('#dc2626')
    if len(data) > 2: p.slices[2].fillColor = HexColor('#eab308')
    if len(data) > 3: p.slices[3].fillColor = HexColor('#22c55e')
    d.add(p); d.add(String(0, 150, "Issue Distribution", fontName=BASE_FONT_BOLD, fontSize=10))
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
    val = _risk_to_value(risk_level); angle_deg = 180 + val * 180.0; rad = math.radians(angle_deg)
    d.add(Line(cx, cy, cx + (r - 10) * math.cos(rad), cy + (r - 10) * math.sin(rad), strokeColor=colors.black, strokeWidth=2))
    d.add(Circle(cx, cy, 4, fillColor=colors.black))
    d.add(String(60, 120, "Risk Meter", fontName=BASE_FONT_BOLD, fontSize=10))
    d.add(String(80, 105, f"{risk_level or 'Medium'}", fontName=BASE_FONT, fontSize=10))
    return d


def _headers_coverage_bar(headers: Dict[str, bool]) -> Drawing:
    items = [
        ("CSP", bool(headers.get("content_security_policy"))),
        ("XFO", bool(headers.get("x_frame_options"))),
        ("XCTO", bool(headers.get("x_content_type_options"))),
        ("HSTS", bool(headers.get("strict_transport_security"))),
        ("Referrer", bool(headers.get("referrer_policy"))),
        ("Permissions", bool(headers.get("permissions_policy"))),
    ]
    w, h = 330, 130; d = Drawing(w, h)
    x0, y0, bar_w, bar_h = 70, 20, 240, 14
    d.add(String(10, h - 12, "Security Headers Coverage", fontName=BASE_FONT_BOLD, fontSize=10))
    for i, (label, present) in enumerate(items):
        y = y0 + i * (bar_h + 8)
        d.add(String(10, y + 2, label, fontName=BASE_FONT, fontSize=9))
        d.add(Rect(x0, y, bar_w, bar_h, strokeColor=HexColor('#e5e7eb'), fillColor=HexColor('#e5e7eb')))
        if present:
            d.add(Rect(x0, y, bar_w, bar_h, strokeColor=None, fillColor=HexColor('#16a34a')))
        else:
            d.add(Rect(x0, y, bar_w * 0.35, bar_h, strokeColor=None, fillColor=HexColor('#dc2626')))
    return d


def _grouped_perf_bars(values: Dict[str, Any]) -> Drawing:
    """
    Grouped bars: Current vs Ideal for CWV (FCP, LCP, Speed Index, TBT, TTI, CLS)
    """
    labels, current, ideal = [], [], []
    pairs = [
        ("FCP", "< 1.8s", values.get("fcp") or values.get("first_contentful_paint") or values.get("load_ms")),
        ("LCP", "< 2.5s", values.get("lcp")),
        ("Speed Index", "< 3.4s", values.get("speed_index")),
        ("TBT", "< 0.2s", values.get("tbt") or values.get("total_blocking_time")),
        ("TTI", "< 3.8s", values.get("tti") or values.get("time_to_interactive")),
        ("CLS", "< 0.10", values.get("cls")),
    ]
    for name, ideal_str, val in pairs:
        if val in (None, "", "N/A"): continue
        labels.append(name)
        if name == "CLS":
            try:
                current.append(float(val))
            except:
                labels.pop(); continue
            ideal.append(0.10)
        else:
            c = _parse_time_to_seconds(val)
            i = _parse_time_to_seconds(ideal_str.replace("<", "").replace(" ", ""))
            if c is None or i is None:
                labels.pop(); continue
            current.append(c); ideal.append(i)
    if not labels:
        d = Drawing(360, 160); d.add(String(0, 140, "Core Web Vitals — (insufficient data for chart)", fontName=BASE_FONT, fontSize=9))
        return d
    d = Drawing(380, 180)
    chart = VerticalBarChart()
    chart.x = 40; chart.y = 30
    chart.height = 120; chart.width = 300
    chart.data = [list(current), list(ideal)]
    chart.categoryAxis.categoryNames = list(labels)
    chart.categoryAxis.labels.boxAnchor = 'n'
    chart.bars[0].fillColor = HexColor('#3b82f6')  # blue current
    chart.bars[1].fillColor = HexColor('#10b981')  # green ideal
    chart.valueAxis.labels.fontName = BASE_FONT
    chart.categoryAxis.labels.fontName = BASE_FONT
    d.add(chart)
    d.add(String(0, 160, "Core Web Vitals — Current vs Ideal", fontName=BASE_FONT_BOLD, fontSize=10))
    return d


def _pass_fail_donut(passed: int, failed: int, title: str) -> Drawing:
    d = Drawing(220, 160)
    p = Pie(); p.x = 40; p.y = 20; p.width = 120; p.height = 120
    p.data = [passed or 0, failed or 0]
    p.labels = [f"Pass ({passed})", f"Fail ({failed})"]
    p.slices[0].fillColor = HexColor('#16a34a'); p.slices[1].fillColor = HexColor('#dc2626')
    d.add(p); d.add(String(0, 145, title, fontName=BASE_FONT_BOLD, fontSize=10))
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
        rows.append([sev, str(counts[sev]["Low"]), str(counts[sev]["Medium"]), str(counts[sev]["High"])])
    t = Table(rows, colWidths=[26*mm, 22*mm, 22*mm, 22*mm])
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f1f5f9')),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 9),
        ('BACKGROUND', (0, 1), (0, 1), HexColor('#dcfce7')),  # Low
        ('BACKGROUND', (0, 2), (0, 2), HexColor('#fef9c3')),  # Medium
        ('BACKGROUND', (0, 3), (0, 3), HexColor('#fee2e2')),  # High
        ('BACKGROUND', (0, 4), (0, 4), HexColor('#fecaca')),  # Critical
    ]))
    return t


# ----- Competitor helpers and charts -----
def _norm_cwv_seconds(val: Any) -> Optional[float]:
    """Normalize CWV-like values to seconds (supports ms/s/float)."""
    try:
        if isinstance(val, (int, float)): return float(val)
        s = str(val).strip().lower()
        if s.endswith("ms"): return float(s.replace("ms", "")) / 1000.0
        if s.endswith("s"):  return float(s.replace("s", "").strip())
        return float(s)
    except Exception:
        return None


def _series_colors():
    # Distinct, accessible palette for up to 5 series
    return [
        HexColor('#2563eb'),  # blue
        HexColor('#16a34a'),  # green
        HexColor('#f59e0b'),  # amber
        HexColor('#ef4444'),  # red
        HexColor('#8b5cf6'),  # violet
    ]


def _multi_grouped_bars(title: str, categories: List[str],
                        series_data: List[List[Optional[float]]],
                        series_names: List[str],
                        width: int = 380, height: int = 180) -> Drawing:
    """
    Builds a grouped bar chart (ReportLab VerticalBarChart).
    Any None values are treated as 0 for drawing.
    """
    d = Drawing(width + 20, height + 40)
    chart = VerticalBarChart()
    chart.x, chart.y = 40, 30
    chart.width, chart.height = width, height
    # sanitize None -> 0 for chart
    data = [[(v if (isinstance(v, (int, float)) and v is not None) else 0.0) for v in row] for row in series_data]
    chart.data = data
    chart.categoryAxis.categoryNames = categories
    chart.categoryAxis.labels.boxAnchor = 'n'
    chart.valueAxis.labels.fontName = BASE_FONT
    chart.categoryAxis.labels.fontName = BASE_FONT

    cols = _series_colors()
    for i, bar in enumerate(chart.bars):
        bar.fillColor = cols[i % len(cols)]

    # Title and simple legend
    x_offset = 0
    d.add(String(0, height + 35, title, fontName=BASE_FONT_BOLD, fontSize=10))
    for i, name in enumerate(series_names):
        d.add(String(0 + x_offset, height + 20, f"■ {name}", fontName=BASE_FONT, fontSize=8, fillColor=cols[i % len(cols)]))
        x_offset += max(60, len(name) * 4 + 30)

    d.add(chart)
    return d


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
# Pages
# ============================================================================
def _page_cover(audit: Dict, styles) -> List[Any]:
    story = []
    logo_path = _safe_get(audit, "logo_path", default=None)
    if isinstance(logo_path, str) and logo_path:
        try:
            img = Image(logo_path, width=60 * mm, height=18 * mm); img.hAlign = 'CENTER'
            story.append(Spacer(1, 12 * mm)); story.append(img)
        except Exception:
            story.append(Spacer(1, 10))
    story.append(Spacer(1, 14 * mm))
    story.append(Paragraph("Comprehensive Website Audit Report", styles['CoverTitle']))
    story.append(Paragraph("Performance • SEO • Security • Accessibility • UX", styles['CoverSubtitle']))
    story.append(Spacer(1, 18 * mm))

    report_id = _safe_get(audit, "report_id", default=None) or _autogen_report_id()
    audited_url = _safe_get(audit, "audited_url", "N/A")
    audit_dt_utc = (
        _safe_get(audit, "audit_datetime_utc", default=None)
        or _safe_get(audit, "audit_datetime", default=None)
        or datetime.utcnow().strftime("%B %d, %Y %H:%M UTC")
    )
    prepared_by = _safe_get(audit, "brand_name", "FF Tech AI")

    rows = [
        ["Website URL", audited_url],
        ["Audit Date & Time (UTC)", audit_dt_utc],
        ["Report ID", report_id],
        ["Prepared By", prepared_by],
    ]
    t = Table(rows, colWidths=[70 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 12),
        ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#334155')),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
        ('BACKGROUND', (0, 0), (0, -1), HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
    ]))
    story.append(t); story.append(Spacer(1, 16 * mm))
    story.append(Paragraph("Confidential – For Client Use Only", styles['Small']))
    story.append(PageBreak()); return story


def _page_summary(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("1. Executive Summary", styles['H1'])]
    overall = _safe_get(audit, "overall_score", 0)
    grade = _safe_get(audit, "grade", _letter_grade(overall))
    risk = _safe_get(audit, "summary", "risk_level", "Medium")
    impact = _safe_get(audit, "summary", "traffic_impact", "N/A")
    story.append(ScoreBar(overall, label="Overall Website Health"))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Grade</b>: {grade}  •  <b>Risk Level</b>: {risk}  •  <b>Impact</b>: {impact}", styles['Body']))

    breakdown = _safe_get(audit, "breakdown", default={})
    sub_rows = [
        ["Performance", f"{int(_safe_get(breakdown,'performance','score',0))}%", _letter_grade(_safe_get(breakdown,'performance','score',0))],
        ["Security", f"{int(_safe_get(breakdown,'security','score',0))}%", _letter_grade(_safe_get(breakdown,'security','score',0))],
        ["SEO", f"{int(_safe_get(breakdown,'seo','score',0))}%", _letter_grade(_safe_get(breakdown,'seo','score',0))],
        ["Accessibility", f"{int(_safe_get(breakdown,'accessibility','score',0))}%", _letter_grade(_safe_get(breakdown,'accessibility','score',0))]
    ]
    sub_tbl = Table([["Category", "Score", "Grade"]] + sub_rows, colWidths=[60 * mm, 28 * mm, 28 * mm])
    sub_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#eef2ff')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10.2),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(Spacer(1, 4)); story.append(sub_tbl)

    issues = _safe_get(audit, "issues", default=[])
    story.append(Spacer(1, 6)); story.append(Paragraph("Top 5 Critical Issues", styles['H2']))
    if issues:
        order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        top5 = sorted(issues, key=lambda x: order.get(str(x.get("severity","")).lower(), 0), reverse=True)[:5]
        for i, it in enumerate(top5, 1):
            story.append(Paragraph(f"{i}. <b>{it.get('issue_name','Issue')}</b> — Severity: <b>{it.get('severity','N/A')}</b> — Page: {_fmt(it.get('affected_page'))}", styles['Body']))
    else:
        story.append(Paragraph("No critical issues detected.", styles['Body']))

    charts = [[_issue_distribution_pie(issues), _risk_meter(risk)]]
    ct = Table(charts, colWidths=[95 * mm, 85 * mm]); ct.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(Spacer(1, 8)); story.append(ct); story.append(PageBreak()); return story


def _page_competitor_comparison(audit: Dict, styles) -> List[Any]:
    comps = _safe_get(audit, "competitors", default=[])
    if not comps or not isinstance(comps, list):
        return []  # nothing to render

    story: List[Any] = [Paragraph("2. Competitor Comparison (Apple-to-Apple)", styles['H1'])]
    comps = comps[:4]  # keep it readable

    # Header labels
    headers = ["Metric", _fmt(_safe_get(audit, "audited_url"))] + [c.get("name") or c.get("url") or f"Competitor {i+1}" for i, c in enumerate(comps)]
    rows = [headers]

    # Your site scores
    your_scores = {
        "overall": _safe_get(audit, "overall_score", default="N/A"),
        "performance": _safe_get(audit, "breakdown", "performance", "score", default="N/A"),
        "seo": _safe_get(audit, "breakdown", "seo", "score", default="N/A"),
        "security": _safe_get(audit, "breakdown", "security", "score", default="N/A"),
        "accessibility": _safe_get(audit, "breakdown", "accessibility", "score", default="N/A"),
    }
    # Your site CWV
    your_cwv = {
        "fcp": _safe_get(audit, "core_web_vitals", "fcp", default=_safe_get(audit, "breakdown", "performance", "extras", "fcp")),
        "lcp": _safe_get(audit, "core_web_vitals", "lcp", default=_safe_get(audit, "breakdown", "performance", "extras", "lcp")),
        "tbt": _safe_get(audit, "core_web_vitals", "tbt", default=_safe_get(audit, "breakdown", "performance", "extras", "tbt")),
        "tti": _safe_get(audit, "core_web_vitals", "tti", default=_safe_get(audit, "breakdown", "performance", "extras", "tti")),
        "cls": _safe_get(audit, "core_web_vitals", "cls", default=_safe_get(audit, "breakdown", "performance", "extras", "cls")),
        "page_size_mb": _safe_get(audit, "core_web_vitals", "page_size_mb", default=None),
        "total_requests": _safe_get(audit, "core_web_vitals", "total_requests", default=None),
    }

    def _score(block: Dict, key: str) -> Any:
        return _safe_get(block, key, default="N/A")

    metric_rows = [
        ("Overall Score (%)", your_scores["overall"], [_score(c.get("scores", {}), "overall") for c in comps]),
        ("Performance Score (%)", your_scores["performance"], [_score(c.get("scores", {}), "performance") for c in comps]),
        ("SEO Score (%)", your_scores["seo"], [_score(c.get("scores", {}), "seo") for c in comps]),
        ("Security Score (%)", your_scores["security"], [_score(c.get("scores", {}), "security") for c in comps]),
        ("Accessibility Score (%)", your_scores["accessibility"], [_score(c.get("scores", {}), "accessibility") for c in comps]),
        ("FCP (s)", _fmt(_norm_cwv_seconds(your_cwv["fcp"])), [_fmt(_norm_cwv_seconds(c.get("cwv", {}).get("fcp"))) for c in comps]),
        ("LCP (s)", _fmt(_norm_cwv_seconds(your_cwv["lcp"])), [_fmt(_norm_cwv_seconds(c.get("cwv", {}).get("lcp"))) for c in comps]),
        ("TBT (s)", _fmt(_norm_cwv_seconds(your_cwv["tbt"])), [_fmt(_norm_cwv_seconds(c.get("cwv", {}).get("tbt"))) for c in comps]),
        ("TTI (s)", _fmt(_norm_cwv_seconds(your_cwv["tti"])), [_fmt(_norm_cwv_seconds(c.get("cwv", {}).get("tti"))) for c in comps]),
        ("CLS", _fmt(your_cwv["cls"]), [_fmt(c.get("cwv", {}).get("cls")) for c in comps]),
        ("Page Size (MB)", _fmt(your_cwv["page_size_mb"]), [_fmt(c.get("cwv", {}).get("page_size_mb")) for c in comps]),
        ("Total Requests", _fmt(your_cwv["total_requests"]), [_fmt(c.get("cwv", {}).get("total_requests")) for c in comps]),
    ]
    for label, yours, others in metric_rows:
        rows.append([label, yours] + others)

    col_w = [48 * mm] + [28 * mm] * (len(headers) - 1)
    tbl = Table(rows, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#dbeafe')),
        ('FONT', (0, 0), (-1, 0), BASE_FONT_BOLD, 10),
        ('FONT', (0, 1), (-1, -1), BASE_FONT, 9.5),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))

    # Charts: Headline Scores (0-100)
    categories = ["Overall", "Performance", "SEO", "Security", "Accessibility"]
    your_scores_series = [
        float(your_scores["overall"] or 0),
        float(your_scores["performance"] or 0),
        float(your_scores["seo"] or 0),
        float(your_scores["security"] or 0),
        float(your_scores["accessibility"] or 0),
    ]
    series_data = [your_scores_series]
    series_names = ["Your Site"]
    for c in comps:
        s = c.get("scores", {})
        series_data.append([
            float(s.get("overall") or 0),
            float(s.get("performance") or 0),
            float(s.get("seo") or 0),
            float(s.get("security") or 0),
            float(s.get("accessibility") or 0),
        ])
        series_names.append(c.get("name") or c.get("url") or "Competitor")
    story.append(_multi_grouped_bars("Headline Scores (0–100)", categories, series_data, series_names))

    # Charts: CWV in seconds (FCP/LCP/TBT/TTI)
    cwv_cats = ["FCP", "LCP", "TBT", "TTI"]
    def cwv_row_from(obj: Optional[Dict]) -> List[Optional[float]]:
        cwv = obj.get("cwv", {}) if obj else {}
        return [
            _norm_cwv_seconds(cwv.get("fcp")),
            _norm_cwv_seconds(cwv.get("lcp")),
            _norm_cwv_seconds(cwv.get("tbt")),
            _norm_cwv_seconds(cwv.get("tti")),
        ]
    your_row = [
        _norm_cwv_seconds(your_cwv["fcp"]),
        _norm_cwv_seconds(your_cwv["lcp"]),
        _norm_cwv_seconds(your_cwv["tbt"]),
        _norm_cwv_seconds(your_cwv["tti"]),
    ]
    cwv_series = [your_row] + [cwv_row_from(c) for c in comps]
    story.append(Spacer(1, 6))
    story.append(_multi_grouped_bars("Core Web Vitals (seconds)", cwv_cats, cwv_series, series_names))

    # Charts: CLS (unitless) – one category, N series
    cls_cats = ["CLS"]
    cls_values = [your_cwv["cls"] if isinstance(your_cwv["cls"], (int, float)) else None]
    for c in comps:
        v = c.get("cwv", {}).get("cls")
        cls_values.append(v if isinstance(v, (int, float)) else None)
    cls_series = [[v] for v in cls_values]  # each series is a [value] list
    story.append(Spacer(1, 6))
    story.append(_multi_grouped_bars("CLS (unitless)", cls_cats, cls_series, series_names, width=200, height=140))

    story.append(PageBreak())
    return story


def _page_overview(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("3. Website Overview", styles['H1'])]
    ov = _safe_get(audit, "website_overview", default={})
    tech_list = _safe_get(ov, "tech_stack", default=[])
    rows = [
        ["Domain Name", _safe_get(ov, "domain_name")],
        ["IP Address", _safe_get(ov, "ip_address")],
        ["Hosting Provider", _safe_get(ov, "hosting_provider")],
        ["Server Location", _safe_get(ov, "server_location")],
        ["CMS Detected", _safe_get(ov, "cms")],
        ["Technology Stack", ", ".join(tech_list) if isinstance(tech_list, list) else _fmt(tech_list)],
        ["SSL Status", _yes_no(_safe_get(ov, "ssl_status"))],
        ["HTTP → HTTPS Redirection", _yes_no(_safe_get(ov, "redirect_http_to_https"))],
        ["robots.txt Status", _yes_no(_safe_get(ov, "robots_txt"))],
        ["sitemap.xml Status", _yes_no(_safe_get(ov, "sitemap_xml"))],
    ]
    hide = bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False))
    rows = _filter_rows(rows, hide)
    tbl = Table(rows, colWidths=[60 * mm, 100 * mm]); tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f1f5f9')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10.5),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(tbl)

    headers = _safe_get(audit, "security_details", "headers", default={})
    story.append(Spacer(1, 8))
    story.append(_headers_coverage_bar(headers))
    story.append(PageBreak()); return story


def _page_performance(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("4. Performance Audit (Core Web Vitals)", styles['H1'])]
    extras = {}
    extras.update(_safe_get(audit, "core_web_vitals", default={}) or {})
    extras.update(_safe_get(audit, "breakdown", "performance", "extras", default={}) or {})

    if "page_size_mb" not in extras and "bytes" in extras:
        try: extras["page_size_mb"] = round(float(extras["bytes"]) / 1024 / 1024, 2)
        except: pass
    if "compression" not in extras:
        if extras.get("brotli"): extras["compression"] = "Brotli"
        elif extras.get("gzip"): extras["compression"] = "GZIP"
        else: extras["compression"] = "None"

    ideal_map = {
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
        "Image Optimization": ("Optimized", "Media performance"),
        "Caching Enabled": ("Yes", "Repeat views"),
        "Compression": ("Brotli/GZIP", "Bandwidth"),
        "CDN Usage": ("Yes", "Edge performance"),
    }
    metrics = [
        ("FCP", extras.get("fcp") or extras.get("first_contentful_paint") or extras.get("load_ms")),
        ("LCP", extras.get("lcp")),
        ("Speed Index", extras.get("speed_index")),
        ("TBT", extras.get("tbt") or extras.get("total_blocking_time")),
        ("TTI", extras.get("tti") or extras.get("time_to_interactive")),
        ("CLS", extras.get("cls")),
        ("Page Size (MB)", extras.get("page_size_mb")),
        ("Total Requests", extras.get("total_requests")),
        ("JS Execution Time", extras.get("js_execution_time") or (extras.get("scripts") and f"{extras.get('scripts')} scripts")),
        ("CSS Size", extras.get("css_size_kb")),
        ("Image Optimization", extras.get("image_optimization_status") or extras.get("image_formats")),
        ("Caching Enabled", extras.get("caching_enabled") or extras.get("cache_headers")),
        ("Compression", extras.get("compression")),
        ("CDN Usage", extras.get("cdn") or extras.get("cdn_usage")),
    ]
    rows = [["Metric", "Value", "Ideal Value", "Status", "Impact"]]
    for m, val in metrics:
        ideal, impact = ideal_map.get(m, ("N/A", "N/A"))
        status = _status_from_value(m, val)
        rows.append([m, _fmt(val), ideal, status, impact])

    hide = bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False))
    rows = _filter_rows(rows, hide)

    tbl = Table(rows, colWidths=[42 * mm, 35 * mm, 34 * mm, 28 * mm, 35 * mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f0fdf4')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))
    story.append(_grouped_perf_bars(extras))

    perf_score = _safe_get(audit, "breakdown", "performance", "score", 0)
    story.append(Spacer(1, 6)); story.append(ScoreBar(perf_score, label="Performance Score"))
    story.append(PageBreak()); return story


def _page_security(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("5. Security Audit (OWASP Based)", styles['H1'])]
    sec = _safe_get(audit, "security_details", default={})
    ssl_rows = [
        ["SSL & Encryption", _yes_no(_safe_get(sec, "ssl_enabled"))],
        ["SSL Validity", _yes_no(_safe_get(sec, "ssl_valid"))],
        ["Certificate Expiry", _safe_get(sec, "cert_expiry", "N/A")],
        ["TLS Version", _safe_get(sec, "tls_version", "N/A")],
        ["Mixed Content", _yes_no(_safe_get(sec, "mixed_content"))],
    ]
    ssl_rows = _filter_rows(ssl_rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    ssl_tbl = Table(ssl_rows, colWidths=[60 * mm, 100 * mm])
    ssl_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafc')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10.2),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(Paragraph("SSL & Encryption", styles['H2'])); story.append(ssl_tbl); story.append(Spacer(1, 6))

    hdr_rows = [["Header", "Present"]]
    hdrs = {
        "content_security_policy": False, "x_frame_options": False, "x_content_type_options": False,
        "strict_transport_security": False, "referrer_policy": False, "permissions_policy": False
    }
    hdrs.update(_safe_get(sec, "headers", default={}) or {})
    for label, key in [
        ("Content-Security-Policy", "content_security_policy"),
        ("X-Frame-Options", "x_frame_options"),
        ("X-Content-Type-Options", "x_content_type_options"),
        ("Strict-Transport-Security", "strict_transport_security"),
        ("Referrer-Policy", "referrer_policy"),
        ("Permissions-Policy", "permissions_policy")
    ]:
        hdr_rows.append([label, _yes_no(hdrs.get(key))])
    hdr_rows = _filter_rows(hdr_rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    hdr_tbl = Table(hdr_rows, colWidths=[78 * mm, 28 * mm]); hdr_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#fff7ed')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(Paragraph("Security Headers", styles['H2'])); story.append(hdr_tbl)
    story.append(Spacer(1, 6)); story.append(_headers_coverage_bar(hdrs))

    vuln = _safe_get(sec, "vulnerabilities", default={})
    vuln_rows = [
        ["SQL Injection Risk", _yes_no(_safe_get(vuln, "sql_injection"))],
        ["XSS Risk", _yes_no(_safe_get(vuln, "xss"))],
        ["CSRF Protection", _yes_no(_safe_get(vuln, "csrf_protection"))],
        ["Open Ports", ", ".join(map(str, _safe_get(vuln, "open_ports", default=[]) or [])) or "N/A"],
        ["Directory Listing Enabled", _yes_no(_safe_get(vuln, "directory_listing"))],
        ["Admin Panel Exposure", _yes_no(_safe_get(vuln, "admin_panel_exposed"))],
        ["Outdated Libraries", ", ".join(_safe_get(vuln, "outdated_libraries", default=[]) or ["N/A"])],
    ]
    vuln_rows = _filter_rows(vuln_rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    v_tbl = Table(vuln_rows, colWidths=[70 * mm, 90 * mm]); v_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#fee2e2')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(Spacer(1, 6)); story.append(Paragraph("Vulnerability Checks", styles['H2'])); story.append(v_tbl)

    issues = _safe_get(audit, "issues", default=[])
    story.append(Spacer(1, 6)); story.append(Paragraph("Risk Heat Map", styles['H2'])); story.append(_risk_heat_map(issues))
    story.append(PageBreak()); return story


def _page_seo(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("6. SEO Audit (Technical + On Page)", styles['H1'])]
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
    tech_rows = _filter_rows(tech_rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    tech_tbl = Table(tech_rows, colWidths=[70 * mm, 80 * mm])
    tech_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafc')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(Paragraph("Technical SEO", styles['H2'])); story.append(tech_tbl)

    present = sum(1 for k in ["meta_title_length", "meta_description_length", "canonical_tag", "schema_markup", "robots_txt", "sitemap"] if seo.get(k))
    total = 6
    story.append(Spacer(1, 6)); story.append(_pass_fail_donut(present, total - present, "Technical Coverage"))

    # On-Page SEO
    onp_rows = [
        ["Keyword Density", _fmt(_safe_get(seo, "keyword_density"))],
        ["Alt Tags on Images", _fmt(_safe_get(seo, "alt_tags"))],
        ["Internal Linking", _fmt(_safe_get(seo, "internal_linking"))],
        ["Page Depth", _fmt(_safe_get(seo, "page_depth"))],
        ["Anchor Text Optimization", _fmt(_safe_get(seo, "anchor_text_optimization"))],
    ]
    onp_rows = _filter_rows(onp_rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    onp_tbl = Table(onp_rows, colWidths=[70 * mm, 80 * mm])
    onp_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#fff7ed')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(Spacer(1, 6)); story.append(Paragraph("On-Page SEO", styles['H2'])); story.append(onp_tbl)

    score = _safe_get(audit, "breakdown", "seo", "score", 0)
    story.append(Spacer(1, 6)); story.append(ScoreBar(score, label="SEO Score"))
    story.append(PageBreak()); return story


def _page_accessibility(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("7. Accessibility Audit (WCAG 2.1)", styles['H1'])]
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
    rows = _filter_rows(rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    tbl = Table(rows, colWidths=[70 * mm, 80 * mm]); tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f0f9ff')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(tbl)

    passed = sum(1 for _, v in rows if v == "Yes")
    failed = sum(1 for _, v in rows if v == "No")
    story.append(Spacer(1, 6)); story.append(_pass_fail_donut(passed, failed, "WCAG Checks"))

    score = _safe_get(audit, "breakdown", "accessibility", "score", 0)
    story.append(Spacer(1, 6)); story.append(ScoreBar(score, label=f"Accessibility Score — Compliance: {_safe_get(acc, 'compliance_level', 'N/A')}"))
    story.append(PageBreak()); return story


def _page_mobile(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("8. Mobile Responsiveness Audit", styles['H1'])]
    mob = _safe_get(audit, "mobile_details", default={})
    rows = [
        ["Viewport Meta Tag", _yes_no(_safe_get(mob, "viewport_meta_tag"))],
        ["Responsive Layout", _yes_no(_safe_get(mob, "responsive_layout"))],
        ["Tap Target Size", _fmt(_safe_get(mob, "tap_target_size"))],
        ["Font Size Readability", _fmt(_safe_get(mob, "font_readability"))],
        ["Mobile Speed Score", _fmt(_safe_get(mob, "mobile_speed_score"))],
        ["Mobile Usability Issues", _fmt(_safe_get(mob, "usability_issues"))],
    ]
    rows = _filter_rows(rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    tbl = Table(rows, colWidths=[70 * mm, 80 * mm]); tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f0fdf4')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(tbl)

    comp = _safe_get(mob, "device_compatibility", default={})
    device_pass = sum(1 for k in ("mobile", "tablet", "desktop") if comp.get(k))
    story.append(Spacer(1, 6)); story.append(_pass_fail_donut(device_pass, 3 - device_pass, "Device Compatibility"))
    story.append(PageBreak()); return story


def _page_ux(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("9. UX / UI Audit (Nielsen Heuristics)", styles['H1'])]
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
    rows = _filter_rows(rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    tbl = Table(rows, colWidths=[70 * mm, 80 * mm]); tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafc')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(tbl)

    ux_score = _safe_get(ux, "score", _safe_get(audit, "breakdown", "links", "score", 0))
    story.append(Spacer(1, 6)); story.append(ScoreBar(ux_score, label="UX Score"))
    story.append(PageBreak()); return story


def _page_compliance(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("10. Compliance & Privacy", styles['H1'])]
    cp = _safe_get(audit, "compliance_privacy", default={})
    rows = [
        ["GDPR Cookie Consent", _yes_no(_safe_get(cp, "gdpr_cookie_consent"))],
        ["Privacy Policy Page", _yes_no(_safe_get(cp, "privacy_policy"))],
        ["Terms & Conditions", _yes_no(_safe_get(cp, "terms_conditions"))],
        ["Cookie Banner", _yes_no(_safe_get(cp, "cookie_banner"))],
        ["Data Collection Transparency", _yes_no(_safe_get(cp, "data_collection_transparency"))],
        ["Third-Party Tracking Scripts", _fmt(_safe_get(cp, "third_party_tracking"))],
    ]
    rows = _filter_rows(rows, bool(_safe_get(audit, "render_options", "hide_empty_rows", default=False)))
    tbl = Table(rows, colWidths=[70 * mm, 80 * mm]); tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#fff7ed')),
        ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
        ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
    ]))
    story.append(tbl); story.append(PageBreak()); return story


def _page_detailed_issues(audit: Dict, styles) -> List[Any]:
    story = [Paragraph("11. Detailed Issue Breakdown", styles['H1'])]
    issues = _safe_get(audit, "issues", default=[])
    if not issues:
        story.append(Paragraph("No issues were provided for breakdown.", styles['Body']))
        return story
    for i, it in enumerate(issues, 1):
        story.append(Paragraph(f"Issue {i}: {it.get('issue_name','Issue')}", styles['H2']))
        rows = [
            ["Category", _fmt(it.get("category"))],
            ["Severity", _fmt(it.get("severity"))],
            ["Status", _fmt(it.get("status", "Open"))],
            ["Affected Page", _fmt(it.get("affected_page"))],
            ["Technical Explanation", _fmt(it.get("technical_explanation"))],
            ["Impact", _fmt(it.get("impact"))],
            ["Estimated Fix Time", _fmt(it.get("estimated_fix_time"))],
        ]
        t = Table(rows, colWidths=[40 * mm, 110 * mm]); t.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), BASE_FONT, 10),
            ('GRID', (0, 0), (-1, -1), 0.4, HexColor('#e5e7eb')),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f8fafc')),
        ]))
        story.append(t); story.append(Spacer(1, 6))
        code = it.get("fix_code_example")
        if code:
            story.append(Paragraph("Fix Code Example:", styles['H3']))
            story.append(Paragraph(f"<font name='{BASE_FONT}' size='9'><br/>{code}</font>", styles['Body']))
        screenshot_path = it.get("screenshot_path")
        if screenshot_path:
            try:
                img = Image(screenshot_path, width=140 * mm, height=70 * mm)
                story.append(Spacer(1, 4)); story.append(img)
            except Exception:
                story.append(Paragraph("Screenshot could not be loaded.", styles['Small']))
        story.append(Spacer(1, 8))
    return story


# ============================================================================
# Master Generator (I/O unchanged)
# ============================================================================
def generate_audit_pdf(audit: Dict[str, Any]) -> bytes:
    styles = get_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=25 * mm, bottomMargin=20 * mm,
        title="Comprehensive Website Audit Report",
        author=_safe_get(audit, "brand_name", "FF Tech AI"),
    )
    story: List[Any] = []
    story.extend(_page_cover(audit, styles))
    story.extend(_page_summary(audit, styles))
    story.extend(_page_competitor_comparison(audit, styles))   # <-- New section (skips if no competitors)
    story.extend(_page_overview(audit, styles))
    story.extend(_page_performance(audit, styles))
    story.extend(_page_security(audit, styles))
    story.extend(_page_seo(audit, styles))
    story.extend(_page_accessibility(audit, styles))
    story.extend(_page_mobile(audit, styles))
    story.extend(_page_ux(audit, styles))
    story.extend(_page_compliance(audit, styles))
    story.extend(_page_detailed_issues(audit, styles))

    # Build with numbered canvas
    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue(); buffer.close(); return pdf_bytes


# ============================================================================
# Optional local demo (keeps I/O unchanged; safe to remove)
# ============================================================================
if __name__ == "__main__":
    sample = {
        "audited_url": "https://example.com",
        "overall_score": 82,
        "grade": "B",
        "audit_datetime": "February 11, 2026",
        "audit_datetime_utc": datetime.utcnow().strftime("%B %d, %Y %H:%M UTC"),
        "brand_name": "FF Tech AI",
        "render_options": {"hide_empty_rows": False},

        "breakdown": {
            "performance": {"score": 88, "extras": {"load_ms": "1450 ms", "bytes": 980000, "scripts": 18, "styles": 6}},
            "seo": {"score": 72, "extras": {"title": "Home - Example", "meta_description_present": True, "h1_count": 1}},
            "security": {"score": 90},
            "accessibility": {"score": 85},
            "links": {"score": 78}
        },

        "core_web_vitals": {
            "fcp": "1.3s", "lcp": "2.4s", "speed_index": "3.1s", "tbt": "180ms",
            "tti": "3.4s", "cls": 0.06, "page_size_mb": 1.9, "total_requests": 48,
            "js_execution_time": "1.8s", "css_size_kb": 180, "image_optimization_status": "Optimized (WebP/AVIF)",
            "caching_enabled": True, "compression": "Brotli", "cdn": True
        },

        "website_overview": {
            "domain_name": "example.com", "ip_address": "93.184.216.34",
            "hosting_provider": "ExampleHost", "server_location": "US",
            "cms": "Custom", "tech_stack": ["React", "Node", "Nginx"],
            "ssl_status": True, "redirect_http_to_https": True, "robots_txt": True, "sitemap_xml": True
        },

        "security_details": {
            "ssl_enabled": True, "ssl_valid": True, "cert_expiry": "2026-12-01", "tls_version": "TLS 1.3",
            "mixed_content": False,
            "headers": {
                "content_security_policy": True, "x_frame_options": True, "x_content_type_options": True,
                "strict_transport_security": True, "referrer_policy": True, "permissions_policy": True
            },
            "vulnerabilities": {
                "sql_injection": False, "xss": False, "csrf_protection": True,
                "open_ports": [80, 443], "directory_listing": False, "admin_panel_exposed": False,
                "outdated_libraries": []
            }
        },

        "seo_details": {
            "meta_title_length": 56, "meta_description_length": 154,
            "heading_structure": "H1 present; H2/H3 structured",
            "canonical_tag": "Present", "schema_markup": "Organization, WebSite",
            "robots_txt": True, "sitemap": True, "broken_links": 0, "redirect_chains": 0, "errors_404": 0,
            "url_structure": "Clean", "mobile_friendliness": "Mobile-friendly",
            "keyword_density": "Balanced", "alt_tags": "OK", "internal_linking": "Healthy",
            "page_depth": "≤ 3 clicks", "anchor_text_optimization": "Good"
        },

        "accessibility_details": {
            "alt_text": True, "color_contrast_ratio": "≥ 4.5:1", "aria_labels": True,
            "keyboard_navigation": True, "form_labels": True, "focus_indicators": True,
            "heading_structure": "Semantic", "skip_links": True, "compliance_level": "AA"
        },

        "mobile_details": {
            "viewport_meta_tag": True, "responsive_layout": True,
            "tap_target_size": "Adequate", "font_readability": "Good",
            "mobile_speed_score": "85/100", "usability_issues": "None",
            "device_compatibility": {"mobile": True, "tablet": True, "desktop": True}
        },

        "ux_details": {
            "navigation_clarity": "Clear", "cta_visibility": "Prominent", "page_load_feedback": "Visible",
            "error_messaging": "Helpful", "form_simplicity": "Simple", "visual_hierarchy": "Strong",
            "trust_signals": "Visible", "consistency": "Consistent", "score": 90
        },

        "compliance_privacy": {
            "gdpr_cookie_consent": True, "privacy_policy": True, "terms_conditions": True,
            "cookie_banner": True, "data_collection_transparency": True, "third_party_tracking": "Analytics"
        },

        "issues": [
            {"issue_name":"Missing Content-Security-Policy","category":"Security","severity":"High","status":"Open",
             "affected_page":"/","technical_explanation":"CSP header absent; risk of XSS.","impact":"High risk",
             "estimated_fix_time":"2–4h","fix_code_example":"Content-Security-Policy: default-src 'self'; ...","likelihood":"High"},
            {"issue_name":"Large LCP due to hero image","category":"Performance","severity":"Medium","status":"Open",
             "affected_page":"/home","technical_explanation":"Hero image not optimized (no AVIF/WebP).",
             "impact":"Slower main content load","estimated_fix_time":"1–2h","likelihood":"Medium"}
        ],

        # --- OPTIONAL: Competitor Comparison (add as many as you like; shown up to 4) ---
        "competitors": [
            {
                "name": "Competitor A",
                "url": "https://comp-a.example",
                "scores": {"overall": 78, "performance": 85, "seo": 72, "security": 90, "accessibility": 80},
                "cwv": {"fcp": "1.4s", "lcp": "2.6s", "tbt": "180ms", "tti": "3.5s", "cls": 0.09, "page_size_mb": 2.1, "total_requests": 52}
            },
            {
                "name": "Competitor B",
                "url": "https://comp-b.example",
                "scores": {"overall": 75, "performance": 80, "seo": 70, "security": 85, "accessibility": 78},
                "cwv": {"fcp": "1.6s", "lcp": "2.9s", "tbt": "210ms", "tti": "3.8s", "cls": 0.11, "page_size_mb": 2.4, "total_requests": 60}
            }
        ]
    }
    with open("comprehensive-website-audit.pdf", "wb") as f:
        f.write(generate_audit_pdf(sample))
    print("Generated: comprehensive-website-audit.pdf")
