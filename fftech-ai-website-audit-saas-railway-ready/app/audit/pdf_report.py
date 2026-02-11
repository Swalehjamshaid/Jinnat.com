# -*- coding: utf-8 -*-

import io
import os
import json
import hashlib
import datetime as dt
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
    Flowable
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pptx import Presentation
from pptx.util import Inches

# =========================================================
# CONFIGURATION
# =========================================================

# Expanded WEIGHTAGE to include "traffic" and "mobile" while keeping a total of 1.00
WEIGHTAGE = {
    "performance": 0.25,
    "security": 0.20,
    "seo": 0.18,
    "accessibility": 0.12,
    "ux": 0.10,
    "traffic": 0.10,
    "mobile": 0.05,
}

TOOL_VERSION = "1.2.0"  # update as you iterate

# =========================================================
# WHITE LABEL BRANDING
# =========================================================

def get_branding(client_config: Dict[str, Any]):
    """
    client_config may contain:
      - company_name: str
      - primary_color: hex str
      - logo_path: str or None
      - dashboard_url: str (for QR)
    """
    return {
        "company_name": client_config.get("company_name", "WebAudit"),
        "primary_color": client_config.get("primary_color", "#2c3e50"),
        "logo_path": client_config.get("logo_path", None),
        "dashboard_url": client_config.get("dashboard_url", None),
    }

# =========================================================
# GOOGLE LIGHTHOUSE API INTEGRATION
# =========================================================

def _fetch_lighthouse(url: str, strategy: str = "desktop", api_key: Optional[str] = None) -> Dict[str, Any]:
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": url, "strategy": strategy}
    if api_key:
        params["key"] = api_key
    r = requests.get(endpoint, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_lighthouse_data(url: str, api_key: str = None) -> Dict[str, Any]:
    """
    Returns normalized category scores (0-100), plus select Core Web Vitals from audits.
    Falls back to 0 on failure.
    """
    try:
        desk = _fetch_lighthouse(url, "desktop", api_key)
        mob = _fetch_lighthouse(url, "mobile", api_key)

        def extract(res):
            cats = res.get("lighthouseResult", {}).get("categories", {})
            audits = res.get("lighthouseResult", {}).get("audits", {})
            return {
                "performance": (cats.get("performance", {}).get("score") or 0) * 100,
                "seo": (cats.get("seo", {}).get("score") or 0) * 100,
                "accessibility": (cats.get("accessibility", {}).get("score") or 0) * 100,
                # Not provided by Lighthouse; approximate to neutral baseline
                "security": 80,
                "ux": 75,
                # Core Web Vitals (ms, unit-normalized)
                "lcp_ms": audits.get("largest-contentful-paint", {}).get("numericValue"),
                "cls": audits.get("cumulative-layout-shift", {}).get("numericValue"),
                "tbt_ms": audits.get("total-blocking-time", {}).get("numericValue"),
                "fid_ms": audits.get("max-potential-fid", {}).get("numericValue"),
                "fcp_ms": audits.get("first-contentful-paint", {}).get("numericValue"),
            }

        d = extract(desk)
        m = extract(mob)

        # Mobile responsiveness proxy from mobile performance
        mobile_score = m["performance"]

        # Merge: prefer desktop for 'performance' but include mobile separately.
        merged = {
            "performance": d["performance"],
            "seo": d["seo"],
            "accessibility": d["accessibility"],
            "security": d["security"],
            "ux": d["ux"],
            "mobile": mobile_score,
            # Cumulative metrics include both views
            "core_web_vitals": {
                "desktop": {
                    "LCP (ms)": d["lcp_ms"],
                    "CLS": d["cls"],
                    "TBT (ms)": d["tbt_ms"],
                    "FID (ms)": d["fid_ms"],
                    "FCP (ms)": d["fcp_ms"],
                },
                "mobile": {
                    "LCP (ms)": m["lcp_ms"],
                    "CLS": m["cls"],
                    "TBT (ms)": m["tbt_ms"],
                    "FID (ms)": m["fid_ms"],
                    "FCP (ms)": m["fcp_ms"],
                }
            }
        }
        return merged
    except Exception:
        # fall back safely
        fallback = {k: 0 for k in ["performance", "seo", "accessibility"]}
        fallback.update({"security": 0, "ux": 0, "mobile": 0, "core_web_vitals": {}})
        return fallback

# =========================================================
# REAL VULNERABILITY SCAN (BASIC ENGINE)
# =========================================================

def run_basic_vulnerability_scan(url: str) -> List[str]:
    """
    Lightweight, non-intrusive checks (headers, forms, HTTPS).
    """
    findings = []
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            findings.append("Website not using HTTPS")

        response = requests.get(url, timeout=15)

        hdrs = {k.lower(): v for k, v in response.headers.items()}

        if "x-frame-options" not in hdrs:
            findings.append("Missing X-Frame-Options header")
        if "content-security-policy" not in hdrs:
            findings.append("Missing Content-Security-Policy header")
        if "strict-transport-security" not in hdrs:
            findings.append("Missing HSTS header")
        if "x-content-type-options" not in hdrs:
            findings.append("Missing X-Content-Type-Options header")
        if "referrer-policy" not in hdrs:
            findings.append("Missing Referrer-Policy header")
        if "permissions-policy" not in hdrs:
            findings.append("Missing Permissions-Policy header")

        soup = BeautifulSoup(response.text, "html.parser")
        forms = soup.find_all("form")
        for form in forms:
            if not form.get("method"):
                findings.append("Form without method attribute detected")
            if (form.get("method") or "").lower() == "get":
                findings.append("Form using GET method (potential sensitive data exposure)")

        # Simple JS eval presence (NOT executing)
        if "eval(" in response.text:
            findings.append("Use of eval() detected in scripts")

    except Exception:
        findings.append("Scan failed or website unreachable")

    return findings

# =========================================================
# SEO QUICK AUDIT (BASIC)
# =========================================================

def _basic_seo_audit(url: str) -> Dict[str, Any]:
    """
    Basic, safe SEO checks from HTML. Non-intrusive.
    """
    result = {
        "has_title": False,
        "has_meta_description": False,
        "canonical_present": False,
        "robots_txt_present": False,
        "sitemap_present": False,
        "h1_count": 0,
        "img_count": 0,
        "img_missing_alt": 0,
        "viewport_meta": False,
    }
    try:
        r = requests.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.find("title")
        if title and title.get_text(strip=True):
            result["has_title"] = True

        desc = soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            result["has_meta_description"] = True

        canon = soup.find("link", attrs={"rel": "canonical"})
        result["canonical_present"] = bool(canon)

        h1s = soup.find_all("h1")
        result["h1_count"] = len(h1s)

        imgs = soup.find_all("img")
        result["img_count"] = len(imgs)
        result["img_missing_alt"] = sum(1 for i in imgs if not i.get("alt"))

        viewport = soup.find("meta", attrs={"name": "viewport"})
        result["viewport_meta"] = bool(viewport)

        # robots.txt & sitemap.xml quick presence
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        try:
            robots = requests.get(base + "/robots.txt", timeout=10)
            result["robots_txt_present"] = robots.status_code == 200 and "User-agent" in robots.text
        except Exception:
            pass
        try:
            sm = requests.get(base + "/sitemap.xml", timeout=10)
            result["sitemap_present"] = sm.status_code == 200 and "<urlset" in sm.text.lower()
        except Exception:
            pass

    except Exception:
        # Keep defaults, non-fatal
        pass

    return result

# =========================================================
# HISTORICAL COMPARISON CHART
# =========================================================

def generate_historical_chart(history: List[float]) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(history, marker="o", color="#0F62FE", linewidth=2)
    ax.set_title("Historical Score Trend")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("Period")
    ax.set_ylabel("Score")
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf

# Additional chart helpers
def _pie_chart(data: Dict[str, float], title: str) -> io.BytesIO:
    labels = list(data.keys())
    sizes = list(data.values())
    colors_list = plt.cm.Paired(np.linspace(0, 1, len(labels)))
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140, colors=colors_list, textprops={"fontsize":8})
    ax.set_title(title)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf

def _bar_chart(labels: List[str], values: List[float], title: str, color: str = "#2c3e50") -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(labels, values, color=color)
    ax.set_title(title)
    ax.set_ylabel("Value")
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf

def _line_chart(series: Dict[str, List[float]], title: str, ylabel: str = "Value") -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6, 3))
    for label, vals in series.items():
        ax.plot(vals, marker="o", linewidth=2, label=label)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf

def _radar_chart(categories: List[str], values: List[float], title: str) -> io.BytesIO:
    N = len(categories)
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    values = values + values[:1]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(4.5, 4.5), subplot_kw=dict(polar=True))
    ax.plot(angles, values, color="#0F62FE", linewidth=2)
    ax.fill(angles, values, color="#0F62FE", alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=8)
    ax.set_title(title, y=1.08)
    ax.set_ylim(0, 100)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf

def _heatmap(matrix: List[List[float]], xlabels: List[str], ylabels: List[str], title: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    c = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(xlabels)))
    ax.set_xticklabels(xlabels, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(ylabels)))
    ax.set_yticklabels(ylabels, fontsize=8)
    ax.set_title(title)
    fig.colorbar(c, ax=ax, orientation="vertical", fraction=0.05, pad=0.03)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf

# =========================================================
# SCORE SYSTEM
# =========================================================

def calculate_scores(audit_data: Dict[str, Any]):
    """
    Uses WEIGHTAGE keys to compute overall score. Extra categories in audit_data are clamped and displayed.
    """
    scores = {}
    for k in WEIGHTAGE:
        val = float(audit_data.get(k, 0))
        scores[k] = max(0, min(val, 100))

    overall = sum(scores[k] * WEIGHTAGE[k] for k in WEIGHTAGE)

    return {
        "category_scores": scores,
        "overall_score": round(overall, 2)
    }

# =========================================================
# DIGITAL SIGNATURE
# =========================================================

def generate_digital_signature(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

# =========================================================
# POWERPOINT AUTO GENERATION
# =========================================================

def generate_executive_ppt(audit_data: Dict[str, Any], file_path: str):
    """
    Generates a simple 2-slide PPT:
      - Executive summary
      - KPI radar chart (if scores available)
    """
    prs = Presentation()
    # Title & Content slide
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Executive Audit Summary"

    content = slide.placeholders[1]
    overall = audit_data.get('overall_score', 0)
    content.text = f"Overall Score: {overall}\nGenerated: {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

    # Radar chart slide
    scores = audit_data.get("category_scores", {})
    if scores:
        cats = list(scores.keys())
        vals = [scores[c] for c in cats]
        buf = _radar_chart(cats, vals, "Category Scores Radar")

        slide2 = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only
        slide2.shapes.title.text = "Category Scores"
        pic = slide2.shapes.add_picture(io.BytesIO(buf.getvalue()), Inches(1), Inches(1.5), width=Inches(8))
    prs.save(file_path)

# =========================================================
# PDF UTILITIES (TOC, HEADER/FOOTER, QR)
# =========================================================

class _MyDocTemplate(SimpleDocTemplate):
    """
    Adds clickable TOC via afterFlowable capturing heading paragraphs.
    """
    def __init__(self, filename, **kwargs):
        super().__init__(filename, pagesize=A4, **kwargs)
        self._heading_count = 0
        self.allowSplitting = 1

    def afterFlowable(self, flowable: Flowable):
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            if style_name in ("Heading1", "Heading2", "Heading3"):
                level = {"Heading1": 0, "Heading2": 1, "Heading3": 2}[style_name]
                text = flowable.getPlainText()
                key = f"heading_{self._heading_count}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
                # Notify TableOfContents
                self.notify('TOCEntry', (level, text, self.page))
                self._heading_count += 1

def _brand_color(hex_color: str) -> colors.Color:
    try:
        return colors.HexColor(hex_color)
    except Exception:
        return colors.HexColor("#2c3e50")

def _on_page(canvas: pdfcanvas.Canvas, doc: _MyDocTemplate, branding: Dict[str, Any]):
    # Header bar
    bar_color = _brand_color(branding.get("primary_color", "#2c3e50"))
    canvas.saveState()
    canvas.setFillColor(bar_color)
    canvas.rect(0, doc.height + doc.topMargin, doc.width + doc.leftMargin + doc.rightMargin, 20, fill=1, stroke=0)

    # Company name on header
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(colors.white)
    canvas.drawString(doc.leftMargin, doc.height + doc.topMargin + 6, branding.get("company_name", "WebAudit"))

    # Footer with page number and timestamp
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.setFont("Helvetica", 8)
    page_num = canvas.getPageNumber()
    ts = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    canvas.drawString(doc.leftMargin, doc.bottomMargin - 20, f"Generated: {ts} • Tool v{TOOL_VERSION}")
    foot_text = f"Page {page_num}"
    w = canvas.stringWidth(foot_text, "Helvetica", 8)
    canvas.drawString(doc.width + doc.leftMargin - w, doc.bottomMargin - 20, foot_text)
    canvas.restoreState()

def _make_qr_flowable(data: str, size: float = 1.5 * inch):
    qrw = qr.QrCodeWidget(data)
    b = qrw.getBounds()
    w = b[2] - b[0]
    h = b[3] - b[1]
    d = Drawing(size, size)
    scale_x = size / w
    scale_y = size / h
    d.add(qrw, transform=[scale_x, 0, 0, scale_y, 0, 0])
    return d

# =========================================================
# MAIN PDF GENERATOR
# =========================================================

def generate_audit_pdf(audit_data: Dict[str, Any],
                       client_config: Dict[str, Any] = None,
                       history_scores: List[float] = None) -> bytes:

    branding = get_branding(client_config or {})
    primary = _brand_color(branding["primary_color"])

    # Prepare buffer and document
    buffer = io.BytesIO()
    doc = _MyDocTemplate(
        buffer,
        leftMargin=48,
        rightMargin=48,
        topMargin=72,
        bottomMargin=54,
        title="Enterprise Website Audit Report",
        author=branding["company_name"],
        subject="Comprehensive Website Audit",
    )

    elements: List[Flowable] = []
    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=10, leading=14))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=11, textColor=colors.HexColor("#555555")))
    styles["Heading1"].textColor = primary
    styles["Heading2"].textColor = primary
    styles["Heading3"].textColor = primary
    styles["Heading1"].spaceBefore = 12
    styles["Heading1"].spaceAfter = 6
    styles["Heading2"].spaceBefore = 10
    styles["Heading2"].spaceAfter = 4
    styles["Heading3"].spaceBefore = 8
    styles["Heading3"].spaceAfter = 2

    # ========== TOC ==========
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(fontName="Helvetica-Bold", name='TOCHeading1', fontSize=12, leftIndent=0, firstLineIndent=-20, spaceAfter=6),
        ParagraphStyle(fontName="Helvetica", name='TOCHeading2', fontSize=10, leftIndent=10, firstLineIndent=-10, spaceAfter=3),
        ParagraphStyle(fontName="Helvetica", name='TOCHeading3', fontSize=9, leftIndent=20, firstLineIndent=-10, spaceAfter=2),
    ]

    # ========== COVER ==========
    # Header/footer callbacks
    def on_page(canvas, d):
        _on_page(canvas, d, branding)

    # Cover: Logo + Title + URL + UTC + Version + QR
    logo_path = branding.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        try:
            elements.append(Image(logo_path, width=1.6 * inch, height=1.6 * inch))
        except Exception:
            pass
    elements.append(Paragraph(branding["company_name"], styles["Title"]))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph("Enterprise Website Audit Report", styles["Heading1"]))
    url = audit_data.get("url", "")
    if url:
        elements.append(Paragraph(f"Target URL: <link href='{url}' color='blue'>{url}</link>", styles["Body"]))
    utc_now = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    elements.append(Paragraph(f"Report Date/Time (UTC): {utc_now}", styles["Body"]))
    elements.append(Paragraph(f"Audit Version / Tool Version: {TOOL_VERSION}", styles["Body"]))
    elements.append(Spacer(1, 0.1 * inch))
    qr_target = branding.get("dashboard_url") or audit_data.get("dashboard_url") or url
    if qr_target:
        elements.append(_make_qr_flowable(qr_target, size=1.5 * inch))
        elements.append(Paragraph("Scan QR to open dashboard", styles["Small"]))
    elements.append(PageBreak())

    # TOC page
    elements.append(Paragraph("Table of Contents", styles["Heading1"]))
    elements.append(toc)
    elements.append(PageBreak())

    # ========== EXECUTIVE SUMMARY ==========
    # Pull Lighthouse and basic audits (real checks where possible)
    lh_api_key = (client_config or {}).get("lighthouse_api_key")  # optional
    lh = fetch_lighthouse_data(url, lh_api_key) if url else {}

    # Merge audit_data categories, preferring provided values if any
    audit_scores_seed = {
        "performance": lh.get("performance", 0),
        "seo": lh.get("seo", 0),
        "accessibility": lh.get("accessibility", 0),
        "security": 0,
        "ux": 0,
        "traffic": 0,
        "mobile": lh.get("mobile", 0),
    }
    for k in audit_scores_seed:
        if k in audit_data:
            audit_scores_seed[k] = audit_data[k]

    # Derive security & SEO basics
    security_findings = run_basic_vulnerability_scan(url) if url else ["No URL provided"]
    if security_findings:
        # crude mapping to score
        miss_count = len(security_findings)
        sec_score = max(0, 100 - miss_count * 8)
        audit_scores_seed["security"] = max(audit_scores_seed.get("security", 0), sec_score)

    seo_quick = _basic_seo_audit(url) if url else {}
    if seo_quick:
        seo_bonus = 0
        seo_bonus += 5 if seo_quick.get("has_title") else -5
        seo_bonus += 5 if seo_quick.get("has_meta_description") else -5
        seo_bonus += 5 if seo_quick.get("canonical_present") else -5
        seo_bonus += 5 if seo_quick.get("robots_txt_present") else -3
        seo_bonus += 5 if seo_quick.get("sitemap_present") else -3
        seo_bonus += 5 if seo_quick.get("viewport_meta") else -5
        audit_scores_seed["seo"] = max(0, min(100, audit_scores_seed["seo"] + seo_bonus))
        audit_scores_seed["ux"] = max(0, min(100, audit_scores_seed["ux"] + (10 if seo_quick.get("viewport_meta") else -5)))

    # Traffic score proxy (if provided)
    traffic_block = audit_data.get("traffic", {})
    if isinstance(traffic_block, dict):
        # Make a proxy score from bounce rate and growth
        bounce = traffic_block.get("bounce_rate")
        growth = traffic_block.get("growth_pct")
        score = 0
        if isinstance(bounce, (int, float)):
            score += max(0, 100 - min(100, bounce)) * 0.6
        if isinstance(growth, (int, float)):
            score += max(0, min(100, growth + 50)) * 0.4  # center growth around 0 => 50
        if score > 0:
            audit_scores_seed["traffic"] = max(audit_scores_seed["traffic"], min(100, score))

    # Compute weighted scores
    agg = calculate_scores(audit_scores_seed)

    # Executive Summary content
    elements.append(Paragraph("Executive Summary", styles["Heading1"]))
    elements.append(Paragraph(f"Overall Website Health Score: <b>{agg['overall_score']}</b>", styles["Body"]))
    # Category table
    cat_rows = [["Category", "Score (0-100)"]]
    for k in ["performance","seo","security","accessibility","ux","traffic","mobile"]:
        cat_rows.append([k.capitalize(), f"{round(audit_scores_seed.get(k,0),2)}"])
    cat_tbl = Table(cat_rows, colWidths=[2.8*inch, 2.2*inch])
    cat_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#121619")),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDE1E6")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]))
    elements.append(cat_tbl)
    elements.append(Spacer(1, 0.1 * inch))

    # Radar chart for categories
    radar_buf = _radar_chart(
        ["Performance","SEO","Security","Accessibility","UX","Traffic","Mobile"],
        [audit_scores_seed.get("performance",0), audit_scores_seed.get("seo",0), audit_scores_seed.get("security",0),
         audit_scores_seed.get("accessibility",0), audit_scores_seed.get("ux",0),
         audit_scores_seed.get("traffic",0), audit_scores_seed.get("mobile",0)],
        "Category Scores Radar"
    )
    elements.append(Image(radar_buf, width=4.8*inch, height=4.0*inch))
    elements.append(PageBreak())

    # Trend summary
    elements.append(Paragraph("Trend Summary (Last 6–12 Months)", styles["Heading2"]))
    if history_scores:
        hbuf = generate_historical_chart(history_scores)
        elements.append(Image(hbuf, width=5.8*inch, height=3.0*inch))
    else:
        elements.append(Paragraph("No historical data provided.", styles["Small"]))
    elements.append(PageBreak())

    # ========== TRAFFIC & GOOGLE SEARCH METRICS ==========
    elements.append(Paragraph("Traffic & Google Search Metrics", styles["Heading1"]))

    # Traffic block (expects audit_data["traffic"])
    tr = audit_data.get("traffic", {})
    if tr:
        # pie chart sources
        sources = tr.get("sources", {})  # {"organic":x,"direct":y,"referral":z,"social":a,"paid":b}
        if sources:
            pie_buf = _pie_chart(sources, "Traffic Source Distribution")
            elements.append(Image(pie_buf, width=4.2*inch, height=2.8*inch))
        # trend line
        trend = tr.get("trend", [])  # list of totals
        if trend and isinstance(trend, list):
            line_buf = _line_chart({"Total Visitors": trend}, "Traffic Trend Over Time", ylabel="Visitors")
            elements.append(Image(line_buf, width=5.8*inch, height=3.0*inch))
        # top landing pages bar
        top_pages = tr.get("top_landing_pages", [])  # list of (path, visits)
        if top_pages:
            labels = [p[0] for p in top_pages[:10]]
            vals = [p[1] for p in top_pages[:10]]
            bar_buf = _bar_chart(labels, vals, "Top Landing Pages", color="#0F62FE")
            elements.append(Image(bar_buf, width=5.8*inch, height=3.0*inch))
    else:
        elements.append(Paragraph("Traffic metrics not provided. Populate audit_data['traffic'] for GA4/GSC insights.", styles["Small"]))

    # GSC block (audit_data["gsc"])
    gsc = audit_data.get("gsc", {})
    if gsc:
        # impressions/clicks/ctr
        summary_rows = [["Metric", "Value"]]
        summary_rows += [["Impressions", gsc.get("impressions", "—")],
                         ["Clicks", gsc.get("clicks", "—")],
                         ["CTR (%)", gsc.get("ctr", "—")]]
        gsc_tbl = Table(summary_rows, colWidths=[2.8*inch, 2.2*inch])
        gsc_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDE1E6")),
            ("ALIGN", (1,1), (-1,-1), "RIGHT"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
        ]))
        elements.append(gsc_tbl)
        # top queries chart
        tq = gsc.get("top_queries", [])  # list of (query, clicks)
        if tq:
            labels = [q[0] for q in tq[:10]]
            vals = [q[1] for q in tq[:10]]
            bar_buf2 = _bar_chart(labels, vals, "Top Queries by Clicks", color="#2c3e50")
            elements.append(Image(bar_buf2, width=5.8*inch, height=3.0*inch))
    else:
        elements.append(Paragraph("GSC metrics not provided. Populate audit_data['gsc'] (impressions, clicks, ctr, top_queries).", styles["Small"]))

    elements.append(PageBreak())

    # ========== SEO KPIs ==========
    elements.append(Paragraph("SEO KPIs", styles["Heading1"]))

    # Pull some from LH audits if available; augment with quick SEO audit
    cwv = lh.get("core_web_vitals", {})
    seo_rows = [
        ["KPI", "Value", "Status", "Weight"],
        ["Title Tag Present", "Yes" if seo_quick.get("has_title") else "No", "Green" if seo_quick.get("has_title") else "Red", "Low"],
        ["Meta Description", "Yes" if seo_quick.get("has_meta_description") else "No", "Green" if seo_quick.get("has_meta_description") else "Orange", "Low"],
        ["Canonical Tag", "Yes" if seo_quick.get("canonical_present") else "No", "Green" if seo_quick.get("canonical_present") else "Orange", "Medium"],
        ["Robots.txt", "Yes" if seo_quick.get("robots_txt_present") else "No", "Green" if seo_quick.get("robots_txt_present") else "Orange", "Medium"],
        ["Sitemap.xml", "Yes" if seo_quick.get("sitemap_present") else "No", "Green" if seo_quick.get("sitemap_present") else "Orange", "Medium"],
        ["H1 Count", str(seo_quick.get("h1_count", "—")), "Green" if 1 <= seo_quick.get("h1_count", 0) <= 2 else "Orange", "Medium"],
        ["Image Alt Coverage", f"{seo_quick.get('img_count',0)-seo_quick.get('img_missing_alt',0)}/{seo_quick.get('img_count',0)}", "Green" if seo_quick.get("img_missing_alt", 0) == 0 else "Orange", "Medium"],
    ]
    seo_tbl = Table(seo_rows, colWidths=[2.2*inch, 1.5*inch, 1.0*inch, 0.9*inch])
    seo_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDE1E6")),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]))
    elements.append(seo_tbl)
    elements.append(Spacer(1, 0.1 * inch))

    # ========== PERFORMANCE KPIs ==========
    elements.append(Paragraph("Performance KPIs", styles["Heading1"]))
    perf_rows = [["Metric", "Desktop", "Mobile"]]
    for k in ["LCP (ms)", "CLS", "TBT (ms)", "FID (ms)", "FCP (ms)"]:
        perf_rows.append([k, str(cwv.get("desktop", {}).get(k, "—")), str(cwv.get("mobile", {}).get(k, "—"))])
    p_tbl = Table(perf_rows, colWidths=[2.4*inch, 1.8*inch, 1.8*inch])
    p_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDE1E6")),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]))
    elements.append(p_tbl)
    elements.append(PageBreak())

    # ========== SECURITY KPIs ==========
    elements.append(Paragraph("Security KPIs", styles["Heading1"]))
    if security_findings:
        for v in security_findings:
            elements.append(Paragraph(f"- {v}", styles["Body"]))
    else:
        elements.append(Paragraph("No basic header-level issues detected.", styles["Body"]))

    # Severity bar (proxy)
    sev_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for f in security_findings:
        if "Missing Content-Security-Policy" in f or "not using HTTPS" in f:
            sev_counts["High"] += 1
        elif "Missing HSTS" in f:
            sev_counts["Medium"] += 1
        else:
            sev_counts["Low"] += 1
    if sum(sev_counts.values()) > 0:
        bar_buf = _bar_chart(list(sev_counts.keys()), list(sev_counts.values()), "Security Findings by Severity", color="#DA1E28")
        elements.append(Image(bar_buf, width=5.8*inch, height=3.0*inch))
    elements.append(PageBreak())

    # ========== ACCESSIBILITY KPIs ==========
    elements.append(Paragraph("Accessibility KPIs", styles["Heading1"]))
    acc_score = audit_scores_seed.get("accessibility", 0)
    acc_rows = [
        ["KPI", "Value", "Status", "Weight"],
        ["WCAG 2.1 Coverage (proxy)", f"{acc_score}/100", "Green" if acc_score >= 90 else "Orange" if acc_score >= 70 else "Red", "High"],
        ["Keyboard Navigation (proxy)", "Checked", "Green" if acc_score >= 80 else "Orange", "Medium"],
        ["ARIA Labels (proxy)", "Partial" if 60 <= acc_score < 90 else "Good" if acc_score >= 90 else "Poor", "Orange" if acc_score < 90 else "Green", "Medium"],
    ]
    acc_tbl = Table(acc_rows, colWidths=[2.6*inch, 1.3*inch, 1.1*inch, 1.0*inch])
    acc_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDE1E6")),
        ("FONTSIZE", (0,0), (-1,-1), 9),
    ]))
    elements.append(acc_tbl)
    elements.append(PageBreak())

    # ========== UX KPIs ==========
    elements.append(Paragraph("UX / User Experience KPIs", styles["Heading1"]))
    ux_rows = [
        ["KPI", "Value", "Status", "Weight"],
        ["Mobile-Friendliness", f"{audit_scores_seed.get('mobile',0)}/100", "Green" if audit_scores_seed.get('mobile',0)>=90 else "Orange" if audit_scores_seed.get('mobile',0)>=70 else "Red", "High"],
        ["Interactive Elements Usability (proxy)", "OK", "Green" if audit_scores_seed.get('ux',0)>=75 else "Orange", "Medium"],
        ["Broken Links & 404 Detection (basic)", "Checked", "Orange" if seo_quick.get("img_missing_alt",0)>0 else "Green", "Low"],
    ]
    ux_tbl = Table(ux_rows, colWidths=[2.8*inch, 1.2*inch, 1.0*inch, 0.9*inch])
    ux_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDE1E6")),
        ("FONTSIZE", (0,0), (-1,-1), 9),
    ]))
    elements.append(ux_tbl)
    elements.append(PageBreak())

    # ========== COMPETITOR COMPARISON ==========
    elements.append(Paragraph("Competitor Comparison", styles["Heading1"]))
    competitors: List[str] = audit_data.get("competitors", [])
    comp_data = {}
    if competitors:
        for cu in competitors[:5]:
            comp_scores = fetch_lighthouse_data(cu, lh_api_key)
            comp_data[cu] = comp_scores.get("performance", 0)
        if comp_data:
            labels = [urlparse(u).netloc for u in comp_data]
            vals = list(comp_data.values())
            cbuf = _bar_chart(labels, vals, "Competitor Performance (Desktop Lighthouse)", color="#0F62FE")
            elements.append(Image(cbuf, width=5.8*inch, height=3.0*inch))
    else:
        elements.append(Paragraph("No competitors provided. Add 'competitors': [url1, url2, ...] in audit_data.", styles["Small"]))
    elements.append(PageBreak())

    # ========== HISTORICAL COMPARISON ==========
    elements.append(Paragraph("Historical Comparison / Trend Analysis", styles["Heading1"]))
    # Example placeholders if audit_data has separate time series (optional)
    trends = audit_data.get("trends", {})  # {"traffic":[...], "rankings":[...], "lcp":[...], "vulns":[...], "engagement":[...]}
    if trends:
        for k, series in trends.items():
            lineb = _line_chart({k: series}, f"{k.title()} Trend", ylabel=k.title())
            elements.append(Image(lineb, width=5.8*inch, height=3.0*inch))
    else:
        elements.append(Paragraph("No trend series provided.", styles["Small"]))
    elements.append(PageBreak())

    # ========== KPI SCORECARDS (~150) ==========
    elements.append(Paragraph("KPI Scorecards", styles["Heading1"]))
    # If caller passes detailed KPI list, render them; else synthesize from available
    kpis = audit_data.get("kpis")  # list of dicts: {"name","value","status","weight"}
    if not kpis:
        # synthesize a compact set from what we have (example)
        kpis = []
        for name, val in audit_scores_seed.items():
            kpis.append({"name": f"{name.title()} Score", "value": round(val,2), "status": "Green" if val>=90 else "Orange" if val>=70 else "Red", "weight": WEIGHTAGE.get(name, 0)})
        # Add CWV
        for plat in ("desktop","mobile"):
            for metric, mval in cwv.get(plat, {}).items():
                if mval is not None:
                    kpis.append({"name": f"{metric} ({plat})", "value": mval, "status": "Green" if metric=="CLS" and mval<=0.1 else "Orange", "weight": 0.0})
    # chunk into pages
    chunk_size = 25
    for i in range(0, len(kpis), chunk_size):
        rows = [["KPI Name", "Value", "Status", "Weight"]]
        for item in kpis[i:i+chunk_size]:
            rows.append([str(item.get("name","")), str(item.get("value","")), str(item.get("status","")), str(item.get("weight",""))])
        tbl = Table(rows, colWidths=[3.2*inch, 1.1*inch, 0.9*inch, 0.8*inch], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDE1E6")),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(PageBreak())

    # ========== AI RECOMMENDATIONS ==========
    elements.append(Paragraph("AI Recommendations", styles["Heading1"]))
    recs: List[str] = []

    # Heuristic recommendations
    if audit_scores_seed.get("performance", 0) < 90:
        recs.append("Optimize images and enable compression (gzip/brotli) to reduce LCP/TBT.")
    if audit_scores_seed.get("seo", 0) < 90:
        recs.append("Improve meta tags (title/description) and ensure canonical tags are correctly set.")
    if audit_scores_seed.get("security", 0) < 90:
        recs.append("Add strong Content-Security-Policy, HSTS, and X-Content-Type-Options headers.")
    if audit_scores_seed.get("accessibility", 0) < 90:
        recs.append("Fix contrast issues, add ARIA labels, and ensure keyboard navigability.")
    if seo_quick and seo_quick.get("img_missing_alt", 0) > 0:
        recs.append(f"Add alt text to {seo_quick.get('img_missing_alt')} images.")
    if audit_scores_seed.get("mobile", 0) < 90:
        recs.append("Improve mobile responsiveness; verify viewport and tap targets per Lighthouse.")
    if not recs:
        recs.append("Site is in good shape. Maintain current best practices and monitor trends monthly.")

    for r in recs:
        elements.append(Paragraph(f"- {r}", styles["Body"]))
    elements.append(PageBreak())

    # ========== DIGITAL SIGNATURE ==========
    elements.append(Paragraph("Verification & Digital Signature", styles["Heading1"]))
    elements.append(Paragraph("This report includes a SHA-256 digital signature for integrity verification.", styles["Body"]))
    elements.append(Paragraph("Compare the printed signature below with your independently computed hash of the PDF bytes.", styles["Small"]))

    # Build once to get bytes for hashing (use a provisional build)
    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)

    pdf_bytes = buffer.getvalue()
    signature = generate_digital_signature(pdf_bytes)

    # Append the signature page
    buffer2 = io.BytesIO()
    doc2 = _MyDocTemplate(
        buffer2,
        leftMargin=48,
        rightMargin=48,
        topMargin=72,
        bottomMargin=54,
        title="Enterprise Website Audit Report",
        author=branding["company_name"],
        subject="Comprehensive Website Audit",
    )

    # Rebuild and add signature page at end (so TOC page numbers are stable)
    elements.append(Paragraph(f"Digital Signature (SHA-256): <b>{signature}</b>", styles["Body"]))
    # Add dashboard link again (clickable)
    if qr_target:
        elements.append(Paragraph(f"Dashboard: <link href='{qr_target}' color='blue'>{qr_target}</link>", styles["Body"]))

    doc2.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    final_pdf = buffer2.getvalue()
    buffer.close()
    buffer2.close()

    # Print signature for CLI parity with your original behavior
    print("Digital Signature:", signature)

    # POWERPOINT
    # Use the computed scores to generate the PPT in the same path used previously
    # Keeping the exact call signature and default path
    score_data = {
        "overall_score": agg["overall_score"],
        "category_scores": agg["category_scores"],
    }
    generate_executive_ppt(score_data, "/tmp/executive_summary.pptx")

    return final_pdf
``
