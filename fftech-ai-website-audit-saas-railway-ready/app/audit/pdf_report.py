# -*- coding: utf-8 -*-

import io
import os
import json
import hashlib
import datetime as dt
from typing import Dict, Any, List, Tuple, Optional

import requests
from bs4 import BeautifulSoup

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image
)
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.pdfgen import canvas

import matplotlib
matplotlib.use("Agg")  # Safe for headless servers/containers
import matplotlib.pyplot as plt
import numpy as np

from pptx import Presentation
from pptx.util import Inches


# =========================================================
# CONFIGURATION
# =========================================================

# NOTE: We preserve the original WEIGHTAGE keys to avoid breaking callers.
# Additional categories like "traffic" and "mobile" are supported for display
# but are not included in the weighted overall score unless you add them here.
WEIGHTAGE = {
    "performance": 0.30,
    "security": 0.25,
    "seo": 0.20,
    "accessibility": 0.15,
    "ux": 0.10,
}

PRIMARY_OK = colors.HexColor("#2ecc71")   # Green
PRIMARY_WARN = colors.HexColor("#f39c12") # Orange
PRIMARY_BAD = colors.HexColor("#e74c3c")  # Red
GRID = colors.HexColor("#DDE1E6")


# =========================================================
# WHITE LABEL BRANDING
# =========================================================

def get_branding(client_config: Dict[str, Any]):
    return {
        "company_name": client_config.get("company_name", "FF Tech"),
        "primary_color": client_config.get("primary_color", "#2c3e50"),
        "logo_path": client_config.get("logo_path", None)
    }


# =========================================================
# OPTIONAL LIGHTHOUSE (SAFE FALLBACK)
# =========================================================

def fetch_lighthouse_data(url: str, api_key: str = None) -> Dict[str, Any]:
    """
    Fetch minimal Lighthouse-like scores from PageSpeed Online.
    If not available or fails, return zeros. This function is optional and
    never blocks PDF generation.
    """
    try:
        endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {"url": url, "strategy": "desktop"}
        if api_key:
            params["key"] = api_key
        resp = requests.get(endpoint, params=params, timeout=15)
        data = resp.json()
        cats = data.get("lighthouseResult", {}).get("categories", {})
        return {
            "performance": cats.get("performance", {}).get("score", 0) * 100,
            "seo": cats.get("seo", {}).get("score", 0) * 100,
            "accessibility": cats.get("accessibility", {}).get("score", 0) * 100,
            # Not directly provided; placeholders if you want
            "security": 80,
            "ux": 75,
        }
    except Exception:
        return {k: 0 for k in WEIGHTAGE}


# =========================================================
# BASIC APP-SIDE CHECKS (REAL-WORLD SAFE HEURISTICS)
# =========================================================

def run_basic_vulnerability_scan(url: str) -> List[str]:
    findings: List[str] = []
    try:
        if not url:
            return ["No URL provided for security scan"]
        r = requests.get(url, timeout=12)
        # Header checks:
        if "X-Frame-Options" not in r.headers:
            findings.append("Missing X-Frame-Options header")
        if "Content-Security-Policy" not in r.headers:
            findings.append("Missing Content-Security-Policy header")
        if "Strict-Transport-Security" not in r.headers and url.startswith("https"):
            findings.append("Missing HSTS header (Strict-Transport-Security)")

        # DOM checks:
        soup = BeautifulSoup(r.text, "html.parser")
        forms = soup.find_all("form")
        for f in forms:
            if not f.get("method"):
                findings.append("Form without method attribute detected")
        # Accessibility quick checks:
        imgs = soup.find_all("img")
        if imgs:
            missing_alt = sum(1 for im in imgs if not im.get("alt"))
            if missing_alt > 0:
                findings.append(f"{missing_alt} image(s) missing alt text")
        # SEO quick checks:
        title_tag = soup.find("title")
        if not title_tag or not title_tag.get_text(strip=True):
            findings.append("Missing or empty <title> tag")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if not meta_desc or not meta_desc.get("content"):
            findings.append("Missing meta description")

        # robots.txt / sitemap hint
        try:
            robots = requests.get(_robots_url(url), timeout=6)
            if robots.status_code == 200:
                if "Sitemap:" not in robots.text:
                    findings.append("robots.txt found but no Sitemap directive present")
            else:
                findings.append("robots.txt not found or unreachable")
        except Exception:
            findings.append("robots.txt check failed")

    except Exception:
        findings.append("Scan failed or website unreachable")

    return findings


def _robots_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}/robots.txt"
    except Exception:
        return url.rstrip("/") + "/robots.txt"


# =========================================================
# SCORING
# =========================================================

def calculate_scores(audit_data: Dict[str, Any]):
    """
    Overall score is computed using WEIGHTAGE keys only (backward compatible).
    We also surface extra categories (traffic, mobile) in the Executive Summary
    if present in audit_data (but they don't affect overall unless added).
    """
    scores: Dict[str, float] = {}
    for k in WEIGHTAGE:
        val = float(audit_data.get(k, 0))
        scores[k] = max(0, min(val, 100))
    overall = sum(scores[k] * WEIGHTAGE[k] for k in WEIGHTAGE)
    return {
        "category_scores": scores,
        "overall_score": round(overall, 2),
    }


def score_to_status(score: float) -> Tuple[str, colors.Color]:
    if score >= 85:
        return "Good", PRIMARY_OK
    if score >= 65:
        return "Warning", PRIMARY_WARN
    return "Critical", PRIMARY_BAD


# =========================================================
# CHART HELPERS
# =========================================================

def _fig_to_buf() -> io.BytesIO:
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150)
    plt.close()
    buf.seek(0)
    return buf


def line_chart(points: List[Tuple[str, float]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    labels = [p[0] for p in points]
    values = [p[1] for p in points]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.plot(labels, values, marker="o", color="#0F62FE")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=25, ha="right")
    return _fig_to_buf()


def bar_chart(items: List[Tuple[str, float]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    labels = [i[0] for i in items]
    values = [i[1] for i in items]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.bar(labels, values, color="#27AE60")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=25, ha="right")
    return _fig_to_buf()


def pie_chart(parts: List[Tuple[str, float]], title: str = "") -> io.BytesIO:
    labels = [p[0] for p in parts]
    sizes = [p[1] for p in parts]
    fig, ax = plt.subplots(figsize=(5, 5))
    if sum(sizes) <= 0:
        sizes = [1 for _ in sizes] or [1]
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140)
    ax.axis("equal")
    ax.set_title(title)
    return _fig_to_buf()


def radar_chart(categories: List[str], values: List[float], title: str = "") -> io.BytesIO:
    # Radar chart expects circular closure
    N = len(categories)
    if N == 0:
        return _empty_chart("No data")
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    values = values[:N]
    values += values[:1]
    angles += angles[:1]

    fig = plt.figure(figsize=(5.6, 5.0))
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_thetagrids(np.degrees(angles[:-1]), categories)
    ax.set_ylim(0, 100)
    ax.plot(angles, values, color="#2F80ED", linewidth=2)
    ax.fill(angles, values, color="#2F80ED", alpha=0.2)
    ax.set_title(title, y=1.1)
    return _fig_to_buf()


def heatmap(matrix: List[List[float]], xlabels: List[str], ylabels: List[str], title: str = "") -> io.BytesIO:
    data = np.array(matrix) if matrix else np.zeros((1, 1))
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    c = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(xlabels)))
    ax.set_yticks(range(len(ylabels)))
    ax.set_xticklabels(xlabels, rotation=35, ha="right")
    ax.set_yticklabels(ylabels)
    ax.set_title(title)
    fig.colorbar(c, ax=ax, fraction=0.046, pad=0.04)
    return _fig_to_buf()


def multi_line_chart(series: Dict[str, List[Tuple[str, float]]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    for name, pts in series.items():
        labels = [p[0] for p in pts]
        values = [p[1] for p in pts]
        ax.plot(labels, values, marker="o", linewidth=2, label=name)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=25, ha="right")
    ax.legend()
    return _fig_to_buf()


def _empty_chart(msg: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.axis("off")
    ax.text(0.5, 0.5, msg, ha="center", va="center")
    return _fig_to_buf()


# =========================================================
# DIGITAL SIGNATURE
# =========================================================

def generate_digital_signature(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# =========================================================
# POWERPOINT AUTO GENERATION (Optional)
# =========================================================

def generate_executive_ppt(audit_data: Dict[str, Any], file_path: str):
    prs = Presentation()
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Executive Audit Summary"
    content = slide.placeholders[1]
    content.text = f"Overall Score: {audit_data.get('overall_score', 0)}"
    prs.save(file_path)


# =========================================================
# DOC WITH CLICKABLE TOC + HEADER/FOOTER
# =========================================================

class _DocWithTOC(SimpleDocTemplate):
    def __init__(self, *args, **kwargs):
        self._heading_styles = {"Heading1": 0, "Heading2": 1}
        super().__init__(*args, **kwargs)

    def afterFlowable(self, flowable):
        from reportlab.platypus import Paragraph
        if isinstance(flowable, Paragraph):
            style_name = getattr(flowable.style, "name", "")
            if style_name in self._heading_styles:
                level = self._heading_styles[style_name]
                text = flowable.getPlainText()
                key = f"h_{hash((text, self.page))}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
                self.notify("TOCEntry", (level, text, self.page))


def _draw_header_footer(c: canvas.Canvas, doc: SimpleDocTemplate, url: str, branding: Dict[str, Any]):
    c.saveState()
    # Header line
    c.setStrokeColor(colors.HexColor(branding.get("primary_color", "#2c3e50")))
    c.setLineWidth(0.6)
    c.line(doc.leftMargin, doc.height + doc.topMargin + 6, doc.width + doc.leftMargin, doc.height + doc.topMargin + 6)
    # Header text
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#525252"))
    header_left = f"{branding.get('company_name', 'FF Tech')} — {url or ''}"
    c.drawString(doc.leftMargin, doc.height + doc.topMargin + 10, header_left[:140])
    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#6F6F6F"))
    page_num = c.getPageNumber()
    timestamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    footer_left = f"Generated: {timestamp}"
    footer_right = f"Page {page_num}"
    c.drawString(doc.leftMargin, doc.bottomMargin - 20, footer_left)
    w = c.stringWidth(footer_right, "Helvetica", 8)
    c.drawString(doc.leftMargin + doc.width - w, doc.bottomMargin - 20, footer_right)
    c.restoreState()


# =========================================================
# MAIN GENERATOR (UNCHANGED SIGNATURE/RETURN)
# =========================================================

def generate_audit_pdf(audit_data: Dict[str, Any],
                       client_config: Dict[str, Any] = None,
                       history_scores: List[float] = None) -> bytes:

    branding = get_branding(client_config or {})

    buf = io.BytesIO()
    doc = _DocWithTOC(
        buf, pagesize=A4,
        leftMargin=36, rightMargin=36, topMargin=54, bottomMargin=54,
        title="FF Tech Web Audit",
        author=branding.get("company_name", "FF Tech")
    )
    styles = getSampleStyleSheet()
    # extra styles
    styles.add(ParagraphStyle(name="KPIHeader", parent=styles["Heading2"],
                              textColor=colors.HexColor(branding.get("primary_color", "#2c3e50"))))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9))
    styles.add(ParagraphStyle(name="Tiny", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6F6F6F")))
    elements: List[Any] = []

    url = audit_data.get("url", "")
    tool_version = audit_data.get("tool_version", "v1.0")

    # -------------------- 1) COVER PAGE --------------------
    logo_path = branding.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        try:
            elements.append(Image(logo_path, width=1.6 * inch, height=1.6 * inch))
        except Exception:
            pass

    elements.append(Paragraph(branding["company_name"], styles["Title"]))
    elements.append(Spacer(1, 0.12 * inch))
    elements.append(Paragraph("FF Tech Web Audit Report", styles["Heading1"]))
    elements.append(Spacer(1, 0.06 * inch))
    elements.append(Paragraph(f"Website: {url}", styles["Normal"]))
    elements.append(Paragraph(f"Domain: {(_safe_domain(url) or '')}", styles["Small"]))
    elements.append(Paragraph(f"Report Time (UTC): {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elements.append(Paragraph(f"Audit/Tool Version: {tool_version}", styles["Normal"]))
    elements.append(Spacer(1, 0.12 * inch))

    dashboard_link = audit_data.get("dashboard_url") or url
    if dashboard_link:
        try:
            qr_code = qr.QrCodeWidget(dashboard_link)
            bounds = qr_code.getBounds()
            w = bounds[2] - bounds[0]
            h = bounds[3] - bounds[1]
            d = Drawing(1.4 * inch, 1.4 * inch, transform=[1.4 * inch / w, 0, 0, 1.4 * inch / h, 0, 0])
            d.add(qr_code)
            elements.append(d)
            if "Caption" in styles:
                elements.append(Paragraph("Scan to view the online audit/dashboard", styles["Caption"]))
        except Exception:
            pass

    elements.append(PageBreak())

    # -------------------- 3) CLICKABLE TOC --------------------
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(fontName="Helvetica-Bold", name="TOCHeading1", fontSize=12, leftIndent=20, firstLineIndent=-10, spaceBefore=6),
        ParagraphStyle(fontName="Helvetica", name="TOCHeading2", fontSize=10, leftIndent=36, firstLineIndent=-10, spaceBefore=2),
    ]
    elements.append(Paragraph("Table of Contents", styles["Heading1"]))
    elements.append(Spacer(1, 0.08 * inch))
    elements.append(toc)
    elements.append(PageBreak())

    # -------------------- 2) EXECUTIVE SUMMARY --------------------
    score_data = calculate_scores(audit_data)
    elements.append(Paragraph("Executive Summary", styles["Heading1"]))
    elements.append(Spacer(1, 0.06 * inch))
    elements.append(Paragraph(f"Overall Website Health Score: <b>{score_data['overall_score']}</b>/100", styles["Normal"]))

    # Category table (includes core categories + optional traffic/mobile if present)
    extra_categories = []
    if "traffic" in audit_data:
        t_score = float(audit_data.get("traffic_score", audit_data.get("traffic", {}).get("score", 0)))
        extra_categories.append(("Traffic & Engagement", t_score))
    if "mobile" in audit_data:
        m_score = float(audit_data.get("mobile", 0))
        extra_categories.append(("Mobile Responsiveness", m_score))

    cat = score_data["category_scores"]
    cat_rows = [["Category", "Score", "Status"]]
    for k in WEIGHTAGE:
        s = cat.get(k, 0)
        status, color_ = score_to_status(s)
        cat_rows.append([k.capitalize(), f"{s:.0f}", status])
    for label, s in extra_categories:
        status, color_ = score_to_status(s)
        cat_rows.append([label, f"{s:.0f}", status])

    table = Table(cat_rows, colWidths=[3.1 * inch, 1.0 * inch, 1.6 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#121619")),
        ("GRID", (0, 0), (-1, -1), 0.25, GRID),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.08 * inch))

    # Trend summary chart if history_scores provided (last 6–12 months)
    if history_scores:
        img = line_chart([(str(i + 1), v) for i, v in enumerate(history_scores)], "Overall Score Trend", "Period", "Score")
        elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))

    # AI recommendations summary
    elements.append(Spacer(1, 0.12 * inch))
    elements.append(Paragraph("AI-Generated Recommendations (Summary)", styles["KPIHeader"]))
    for rec in _collect_ai_recommendations(audit_data, score_data):
        elements.append(Paragraph(f"- {rec}", styles["Normal"]))

    elements.append(PageBreak())

    # -------------------- 4) TRAFFIC & GOOGLE SEARCH METRICS --------------------
    traffic = audit_data.get("traffic") or {}
    gsc = audit_data.get("gsc") or {}

    elements.append(Paragraph("Traffic & Google Search Metrics", styles["Heading1"]))
    if traffic:
        # Line chart: traffic trend
        if isinstance(traffic.get("trend"), list) and traffic["trend"]:
            try:
                trend_points = [(str(p[0]), float(p[1])) for p in traffic["trend"]]
                img = line_chart(trend_points, "Traffic Trend (Visits/Sessions)", "Period", "Traffic")
                elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
            except Exception:
                pass
        # Pie chart: source distribution
        if isinstance(traffic.get("sources"), dict) and traffic["sources"]:
            try:
                parts = [(k, float(v)) for k, v in traffic["sources"].items()]
                img = pie_chart(parts, "Traffic Sources")
                elements.append(Image(img, width=4.8 * inch, height=4.8 * inch))
            except Exception:
                pass
        # Bar chart: top landing pages
        if isinstance(traffic.get("top_pages"), list) and traffic["top_pages"]:
            try:
                top_pages = traffic["top_pages"][:10]
                items = [(str(p.get("path") or p.get("url") or f"p{i+1}")[:24], float(p.get("visits", 0))) for i, p in enumerate(top_pages)]
                img = bar_chart(items, "Top Landing Pages (Visits)", "Page", "Visits")
                elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
            except Exception:
                pass

        # Table of GA/GA4 metrics if provided
        ga_rows = []
        def _add_row(label, key):
            v = traffic.get(key)
            if v is not None:
                ga_rows.append([label, str(v)])
        _add_row("Total Visitors", "total_visitors")
        _add_row("Organic Traffic", "organic")
        _add_row("Direct", "direct")
        _add_row("Referral", "referral")
        _add_row("Social", "social")
        _add_row("Paid", "paid")
        _add_row("Bounce Rate (%)", "bounce_rate")
        _add_row("Avg. Session Duration (s)", "avg_session_duration")
        _add_row("Pageviews per Session", "pages_per_session")

        if ga_rows:
            t = Table([["Metric", "Value"]] + ga_rows, colWidths=[2.6 * inch, 1.6 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, GRID),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]))
            elements.append(t)

    if gsc:
        # KPIs: impressions, clicks, ctr
        gsc_rows = []
        for lbl, key in [("Impressions", "impressions"), ("Clicks", "clicks"), ("CTR (%)", "ctr")]:
            if key in gsc:
                gsc_rows.append([lbl, str(gsc.get(key))])
        if gsc_rows:
            t = Table([["GSC Metric", "Value"]] + gsc_rows, colWidths=[2.6 * inch, 1.6 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, GRID),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]))
            elements.append(t)

        # Bar chart: top queries
        if isinstance(gsc.get("queries"), list) and gsc["queries"]:
            try:
                top_q = gsc["queries"][:10]
                items = [(str(q.get("query", ""))[:24], float(q.get("clicks", 0))) for q in top_q]
                img = bar_chart(items, "Top Queries by Clicks", "Query", "Clicks")
                elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
            except Exception:
                pass

    elements.append(PageBreak())

    # -------------------- 5) SEO KPIs (~40) --------------------
    elements.append(Paragraph("SEO KPIs", styles["Heading1"]))
    seo_rows = _build_seo_kpis_table(url, audit_data)
    if seo_rows:
        t = _kpi_scorecard_table(seo_rows)
        elements.append(t)
    # Example chart: Page speed histogram (if provided)
    if isinstance(audit_data.get("page_speed_hist"), list) and audit_data["page_speed_hist"]:
        try:
            pairs = [(str(b), float(v)) for b, v in audit_data["page_speed_hist"]]
            img = bar_chart(pairs, "Page Speed Histogram (ms buckets)", "Bucket", "Pages")
            elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
        except Exception:
            pass
    elements.append(PageBreak())

    # -------------------- 6) PERFORMANCE KPIs (~20) --------------------
    elements.append(Paragraph("Performance KPIs", styles["Heading1"]))
    perf_rows = _build_performance_kpis_table(audit_data)
    if perf_rows:
        elements.append(_kpi_scorecard_table(perf_rows))
    # Trend charts if present
    if isinstance(audit_data.get("perf_trend"), list) and audit_data["perf_trend"]:
        try:
            pts = [(str(p[0]), float(p[1])) for p in audit_data["perf_trend"]]
            img = line_chart(pts, "Load Time Trend (ms)", "Period", "ms")
            elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
        except Exception:
            pass
    elements.append(PageBreak())

    # -------------------- 7) SECURITY KPIs (15–20) --------------------
    elements.append(Paragraph("Security KPIs", styles["Heading1"]))
    sec_rows = _build_security_kpis_table(url, audit_data)
    if sec_rows:
        elements.append(_kpi_scorecard_table(sec_rows))
    # Heatmap for vulnerability severities
    if isinstance(audit_data.get("vuln_heatmap"), dict) and audit_data["vuln_heatmap"]:
        try:
            sev = ["Critical", "High", "Medium", "Low"]
            months = list(audit_data["vuln_heatmap"].keys())[:12]
            matrix = []
            for m in months:
                row = audit_data["vuln_heatmap"][m]
                matrix.append([float(row.get(s, 0)) for s in sev])
            # transpose to severity rows
            matrix_T = np.array(matrix).T.tolist()
            img = heatmap(matrix_T, months, sev, "Vulnerability Severity Heatmap")
            elements.append(Image(img, width=6.2 * inch, height=3.6 * inch))
        except Exception:
            pass
    # Basic findings from our simple scan:
    findings = run_basic_vulnerability_scan(url)
    if findings:
        elements.append(Paragraph("Automated Quick Findings", styles["KPIHeader"]))
        for f in findings:
            elements.append(Paragraph(f"- {f}", styles["Normal"]))
    elements.append(PageBreak())

    # -------------------- 8) ACCESSIBILITY KPIs (15–20) --------------------
    elements.append(Paragraph("Accessibility KPIs", styles["Heading1"]))
    acc_rows = _build_accessibility_kpis_table(audit_data)
    if acc_rows:
        elements.append(_kpi_scorecard_table(acc_rows))
    # Radar chart of accessibility sub-scores if provided
    acc_radar = audit_data.get("accessibility_radar") or {}
    if acc_radar:
        cats = list(acc_radar.keys())
        vals = [float(acc_radar[c]) for c in cats]
        img = radar_chart(cats, vals, "Accessibility Radar")
        elements.append(Image(img, width=5.2 * inch, height=4.8 * inch))
    elements.append(PageBreak())

    # -------------------- 9) UX / USER EXPERIENCE KPIs (15–20) --------------------
    elements.append(Paragraph("UX / User Experience KPIs", styles["Heading1"]))
    ux_rows = _build_ux_kpis_table(audit_data)
    if ux_rows:
        elements.append(_kpi_scorecard_table(ux_rows))
    # Radar chart for UX
    ux_radar = audit_data.get("ux_radar") or {}
    if ux_radar:
        cats = list(ux_radar.keys())
        vals = [float(ux_radar[c]) for c in cats]
        img = radar_chart(cats, vals, "UX Radar")
        elements.append(Image(img, width=5.2 * inch, height=4.8 * inch))
    elements.append(PageBreak())

    # -------------------- 🔟 COMPETITOR COMPARISON --------------------
    elements.append(Paragraph("Competitor Comparison", styles["Heading1"]))
    competitors = audit_data.get("competitors") or []
    if competitors:
        # Multi-line chart of traffic trend
        series = {}
        for comp in competitors[:5]:
            name = comp.get("name") or comp.get("domain") or "Competitor"
            trend = comp.get("traffic_trend") or []
            series[name] = [(str(p[0]), float(p[1])) for p in trend][:12]
        if series:
            img = multi_line_chart(series, "Traffic vs Competitors", "Period", "Traffic")
            elements.append(Image(img, width=6.2 * inch, height=3.6 * inch))
        # Stacked or side-by-side bars for SEO score comparison
        seo_comp = []
        for comp in competitors[:5]:
            name = comp.get("name") or comp.get("domain") or "Competitor"
            seo_comp.append((name[:20], float(comp.get("seo", 0))))
        if seo_comp:
            img = bar_chart(seo_comp, "SEO Performance (Score)", "Competitor", "Score")
            elements.append(Image(img, width=6.2 * inch, height=3.6 * inch))
    else:
        elements.append(Paragraph("No competitor dataset provided.", styles["Small"]))
    elements.append(PageBreak())

    # -------------------- 1️⃣1️⃣ HISTORICAL COMPARISON / TRENDS --------------------
    elements.append(Paragraph("Historical Comparison / Trend Analysis", styles["Heading1"]))
    hist = audit_data.get("history") or {}
    # Generic series: traffic, keyword_rank, page_speed, sec_vulns, engagement
    for key, label, ylabel in [
        ("traffic", "Traffic Trend", "Traffic"),
        ("keyword_rank", "Keyword Ranking Trend", "Avg Rank"),
        ("page_speed", "Page Speed Trend (ms)", "ms"),
        ("sec_vulns", "Security Vulnerabilities Trend", "Count"),
        ("engagement", "Engagement Trend (Pages/Session)", "Pages/Session"),
    ]:
        if key in hist and isinstance(hist[key], list) and hist[key]:
            try:
                pts = [(str(p[0]), float(p[1])) for p in hist[key]][:12]
                img = line_chart(pts, label, "Period", ylabel)
                elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
            except Exception:
                pass
    elements.append(PageBreak())

    # -------------------- 1️⃣3️⃣ KPI SCORECARDS (ALL) --------------------
    elements.append(Paragraph("KPI Scorecards (Consolidated)", styles["Heading1"]))
    all_scorecards = audit_data.get("scorecards") or []
    # expected row dict: {"name": str, "value": str/float, "status": "Good/Warning/Critical", "weight": float, "link": str(optional)}
    if all_scorecards:
        elements.append(_kpi_scorecard_table(all_scorecards, show_weight=True, show_link=True))
    else:
        elements.append(Paragraph("No consolidated KPI scorecard supplied.", styles["Small"]))
    elements.append(PageBreak())

    # -------------------- 1️⃣4️⃣ AI RECOMMENDATIONS (DETAILED) --------------------
    elements.append(Paragraph("AI Recommendations (Detailed)", styles["Heading1"]))
    ai_recs = _collect_ai_recommendations(audit_data, score_data)
    if ai_recs:
        for r in ai_recs:
            elements.append(Paragraph(f"- {r}", styles["Normal"]))
    else:
        elements.append(Paragraph("No AI recommendations provided or generated.", styles["Small"]))

    # -------------------- BUILD DOC --------------------
    def _first(c, d): _draw_header_footer(c, d, url, branding)
    def _later(c, d): _draw_header_footer(c, d, url, branding)
    doc.build(elements, onFirstPage=_first, onLaterPages=_later)

    pdf_bytes = buf.getvalue()
    buf.close()

    # Signature (stdout/log)
    signature = generate_digital_signature(pdf_bytes)
    print("Digital Signature:", signature)

    # Optional PPT (kept for backward compatibility)
    try:
        generate_executive_ppt({"overall_score": score_data["overall_score"]}, "/tmp/executive_summary.pptx")
    except Exception:
        pass

    return pdf_bytes


# =========================================================
# HELPERS FOR KPI TABLES / RECOMMENDATIONS
# =========================================================

def _kpi_scorecard_table(rows: List[Dict[str, Any]], show_weight: bool = False, show_link: bool = False) -> Table:
    """
    rows: list of dicts
      - name (str), value (str/float), status (Good/Warning/Critical), weight (optional float), link (optional)
    """
    headers = ["KPI Name", "Value", "Status"]
    col_widths = [3.1 * inch, 1.1 * inch, 1.0 * inch]
    if show_weight:
        headers.append("Weight")
        col_widths.append(0.9 * inch)
    if show_link:
        headers.append("Link")
        col_widths.append(1.3 * inch)

    data = [headers]
    for r in rows:
        name = str(r.get("name", ""))
        value = r.get("value", "")
        status = str(r.get("status", ""))
        weight = r.get("weight", "")
        link = r.get("link", "")
        row = [name, str(value), status]
        if show_weight:
            row.append(f"{weight}" if isinstance(weight, (int, float)) else str(weight))
        if show_link:
            row.append(str(link)[:60] if link else "")
        data.append(row)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#121619")),
        ("GRID", (0, 0), (-1, -1), 0.25, GRID),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]
    # Status colors
    for r_i in range(1, len(data)):
        try:
            status = (data[r_i][2] or "").strip().lower()
            if status.startswith("good"):
                styles.append(("TEXTCOLOR", (2, r_i), (2, r_i), PRIMARY_OK))
            elif status.startswith("warn"):
                styles.append(("TEXTCOLOR", (2, r_i), (2, r_i), PRIMARY_WARN))
            else:
                styles.append(("TEXTCOLOR", (2, r_i), (2, r_i), PRIMARY_BAD))
        except Exception:
            pass

    t.setStyle(TableStyle(styles))
    return t


def _build_seo_kpis_table(url: str, audit_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build ~40 SEO KPIs if available (mix of provided + quick checks).
    Accepts optional audit_data['seo_kpis'] to override/enhance.
    """
    rows: List[Dict[str, Any]] = []
    custom = audit_data.get("seo_kpis") or []
    rows.extend(custom)

    # Quick checks from live HTML (best effort)
    try:
        if url:
            r = requests.get(url, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            title = (soup.find("title").get_text(strip=True) if soup.find("title") else "")
            meta_desc = soup.find("meta", attrs={"name": "description"})
            desc = (meta_desc.get("content") if meta_desc else "")
            h1_count = len(soup.find_all("h1"))
            h2_count = len(soup.find_all("h2"))
            h3_count = len(soup.find_all("h3"))
            robots = _robots_fetch(url)

            rows += [
                {"name": "Title Tag Present", "value": "Yes" if title else "No", "status": "Good" if title else "Critical"},
                {"name": "Meta Description Present", "value": "Yes" if desc else "No", "status": "Good" if desc else "Warning"},
                {"name": "H1 Count", "value": h1_count, "status": "Good" if h1_count == 1 else "Warning"},
                {"name": "H2 Count", "value": h2_count, "status": "Good" if h2_count >= 1 else "Warning"},
                {"name": "H3 Count", "value": h3_count, "status": "Good" if h3_count >= 1 else "Warning"},
                {"name": "robots.txt Present", "value": "Yes" if robots["ok"] else "No", "status": "Good" if robots["ok"] else "Warning"},
                {"name": "Sitemap Declared in robots.txt", "value": robots["sitemap"], "status": "Good" if robots["sitemap"] == "Yes" else "Warning"},
            ]
    except Exception:
        rows.append({"name": "Live SEO Checks", "value": "Unavailable", "status": "Warning"})

    # Fill the rest with provided aggregates if present
    for label_key in [
        "canonical_tags", "broken_links_404", "index_coverage_ok", "internal_linking_score",
        "image_alt_coverage", "mobile_responsiveness", "structured_data", "keyword_density_ok",
        "backlink_count", "backlink_quality", "competitor_seo_relative",
    ]:
        if label_key in audit_data:
            val = audit_data[label_key]
            status, _ = score_to_status(float(val)) if isinstance(val, (int, float)) else ("Good", PRIMARY_OK)
            rows.append({"name": label_key.replace("_", " ").title(), "value": val, "status": status})

    return rows[:40]  # cap at ~40 for layout consistency


def _build_performance_kpis_table(audit_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    perf = audit_data.get("performance_kpis") or {}
    def add(name, key, warn_gt=None):
        v = perf.get(key, audit_data.get(key))
        if v is None:
            return
        status = "Good"
        try:
            fv = float(v)
            if warn_gt and fv > warn_gt:
                status = "Warning"
        except Exception:
            pass
        rows.append({"name": name, "value": v, "status": status})

    add("Page Load Speed (ms)", "page_load_ms", warn_gt=3000)
    add("Time To First Byte (ms)", "ttfb", warn_gt=800)
    add("Render Start (ms)", "render_start_ms", warn_gt=1200)
    add("Fully Loaded (ms)", "fully_loaded_ms", warn_gt=4000)
    add("HTTP Requests (count)", "http_requests", warn_gt=100)
    add("Page Weight (MB)", "page_weight_mb", warn_gt=4)
    add("Caching Efficiency (%)", "caching_efficiency")
    add("Compression (gzip/brotli)", "compression")
    add("CDN Present", "cdn_present")
    add("CDN Avg Speed (ms)", "cdn_speed_ms", warn_gt=200)

    # Add extra metrics if provided:
    for k, v in perf.items():
        if all(k not in r["name"].lower() for r in rows):
            rows.append({"name": k.replace("_", " ").title(), "value": v, "status": "Good"})

    return rows[:20]


def _build_security_kpis_table(url: str, audit_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    sec = audit_data.get("security_kpis") or {}

    def add(name, key, yes_good=True):
        v = sec.get(key, audit_data.get(key))
        if v is None:
            return
        val = str(v)
        status = "Good" if ((val.lower() in ["true", "yes", "1"] or (isinstance(v, (int, float)) and v > 0)) if yes_good else False) else "Warning"
        rows.append({"name": name, "value": val, "status": status})

    add("HTTPS / TLS", "https_tls")
    add("HSTS Header", "hsts")
    add("Content-Security-Policy", "csp")
    add("X-Frame-Options", "x_frame_options")
    add("X-XSS-Protection", "x_xss_protection")
    add("SSL Labs Rating", "ssl_labs_rating")  # value like A+, A, B...
    add("SQLi Checks", "sqli_ok")
    add("XSS Checks", "xss_ok")
    add("CSRF Checks", "csrf_ok")
    add("OWASP Top 10 Coverage", "owasp_top10")

    # add counts if provided
    for key in ["critical_vulns", "high_vulns", "medium_vulns", "low_vulns"]:
        if key in sec:
            v = float(sec[key])
            status, _ = score_to_status(100 - min(100, v * 10))
            rows.append({"name": key.replace("_", " ").title(), "value": v, "status": status})

    return rows[:20]


def _build_accessibility_kpis_table(audit_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    acc = audit_data.get("accessibility_kpis") or {}

    def add(name, key):
        v = acc.get(key, audit_data.get(key))
        if v is None:
            return
        status, _ = score_to_status(float(v)) if isinstance(v, (int, float)) else ("Good", PRIMARY_OK)
        rows.append({"name": name, "value": v, "status": status})

    add("WCAG 2.1 Compliance (%)", "wcag_compliance")
    add("Contrast Ratio Issues (count)", "contrast_issues")
    add("Keyboard Navigation Issues", "keyboard_issues")
    add("Missing ARIA Labels (count)", "aria_missing")
    add("Alt Text Coverage (%)", "alt_coverage")
    add("Screen Reader Compatibility (%)", "screen_reader_compat")

    # fill up with any extras provided
    for k, v in acc.items():
        if all(k.replace("_", " ").title() != r["name"] for r in rows):
            rows.append({"name": k.replace("_", " ").title(), "value": v, "status": "Good"})

    return rows[:20]


def _build_ux_kpis_table(audit_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    ux = audit_data.get("ux_kpis") or {}

    def add(name, key):
        v = ux.get(key, audit_data.get(key))
        if v is None:
            return
        status, _ = score_to_status(float(v)) if isinstance(v, (int, float)) else ("Good", PRIMARY_OK)
        rows.append({"name": name, "value": v, "status": status})

    add("Mobile-Friendliness Score (%)", "mobile_friendly")
    add("Interactive Elements Usability (%)", "interactive_usability")
    add("Broken Links & 404 (count)", "broken_links_count")
    add("CTA Visibility & Clicks (score)", "cta_score")
    add("Form Validation Errors (count)", "form_errors")
    add("Popup/Modal Impact (score)", "popup_impact")

    # fill up with extras
    for k, v in ux.items():
        if all(k.replace("_", " ").title() != r["name"] for r in rows):
            rows.append({"name": k.replace("_", " ").title(), "value": v, "status": "Good"})

    return rows[:20]


def _robots_fetch(url: str) -> Dict[str, str]:
    try:
        r = requests.get(_robots_url(url), timeout=6)
        if r.status_code == 200:
            return {"ok": "Yes", "sitemap": "Yes" if "Sitemap:" in r.text else "No"}
        return {"ok": "No", "sitemap": "No"}
    except Exception:
        return {"ok": "No", "sitemap": "No"}


def _safe_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return p.netloc
    except Exception:
        return ""


def _collect_ai_recommendations(audit_data: Dict[str, Any], score_data: Dict[str, Any]) -> List[str]:
    # If provided externally, use them:
    provided = audit_data.get("ai_recommendations")
    if isinstance(provided, list) and provided:
        return [str(x) for x in provided][:15]

    # Otherwise generate simple rule-based suggestions from category scores:
    recs: List[str] = []
    cats = score_data.get("category_scores", {})
    def add(msg): 
        if msg not in recs: 
            recs.append(msg)

    # SEO
    if cats.get("seo", 100) < 80:
        add("Add or improve meta descriptions and ensure a single H1 per page; audit robots.txt and sitemap.")
        add("Enhance internal linking and image alt coverage; implement structured data (Schema.org) where relevant.")
    # Performance
    if cats.get("performance", 100) < 80:
        add("Optimize images (compression, next-gen formats), enable brotli/gzip, leverage caching and a CDN.")
        add("Reduce render-blocking JS/CSS and minimize third-party scripts; aim for LCP < 2.5s.")
    # Security
    if cats.get("security", 100) < 85:
        add("Enforce HTTPS with HSTS; set CSP, X-Frame-Options, and X-XSS-Protection headers.")
        add("Perform regular OWASP Top 10 checks; review SSL/TLS configuration.")
    # Accessibility
    if cats.get("accessibility", 100) < 85:
        add("Improve color contrast, add ARIA labels, and ensure keyboard navigability across all components.")
        add("Increase alt text coverage and test with screen readers (NVDA/VoiceOver).")
    # UX
    if cats.get("ux", 100) < 85:
        add("Improve mobile tap targets, simplify forms, and prioritize clear CTAs above the fold.")
        add("Reduce intrusive pop-ups and ensure consistent component behavior.")
    return recs[:15]
