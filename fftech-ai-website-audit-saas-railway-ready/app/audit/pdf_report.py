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
matplotlib.use('Agg')  # Non-GUI backend for servers
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches


# =========================================================
# CONFIGURATION
# =========================================================

WEIGHTAGE = {
    "performance": 0.30,
    "security": 0.25,
    "seo": 0.20,
    "accessibility": 0.15,
    "ux": 0.10
}


# =========================================================
# WHITE LABEL BRANDING
# =========================================================

def get_branding(client_config: Dict[str, Any]):
    return {
        "company_name": client_config.get("company_name", "WebAudit"),
        "primary_color": client_config.get("primary_color", "#2c3e50"),
        "logo_path": client_config.get("logo_path", None)
    }


# =========================================================
# GOOGLE LIGHTHOUSE API INTEGRATION (optional helper)
# =========================================================

def fetch_lighthouse_data(url: str, api_key: str = None) -> Dict[str, Any]:
    """Fetches basic scores from Google PageSpeed (Lighthouse).
    Safe fallback to zeros on failure. Does not block PDF generation."""
    try:
        endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {"url": url, "strategy": "desktop"}
        if api_key:
            params["key"] = api_key

        response = requests.get(endpoint, params=params, timeout=15)
        data = response.json()

        categories = data.get("lighthouseResult", {}).get("categories", {})
        return {
            "performance": categories.get("performance", {}).get("score", 0) * 100,
            "seo": categories.get("seo", {}).get("score", 0) * 100,
            "accessibility": categories.get("accessibility", {}).get("score", 0) * 100,
            "security": 80,  # Lighthouse doesn't provide real security
            "ux": 75
        }
    except Exception:
        return {k: 0 for k in WEIGHTAGE}


# =========================================================
# BASIC VULNERABILITY SCAN (headers + forms)
# =========================================================

def run_basic_vulnerability_scan(url: str) -> List[str]:
    findings: List[str] = []
    try:
        if not url:
            return ["No URL provided for security scan"]
        response = requests.get(url, timeout=10)

        if "X-Frame-Options" not in response.headers:
            findings.append("Missing X-Frame-Options header")

        if "Content-Security-Policy" not in response.headers:
            findings.append("Missing Content-Security-Policy header")

        if "Strict-Transport-Security" not in response.headers:
            findings.append("Missing HSTS header")

        soup = BeautifulSoup(response.text, "html.parser")
        forms = soup.find_all("form")
        for form in forms:
            if not form.get("method"):
                findings.append("Form without method attribute detected")

    except Exception:
        findings.append("Scan failed or website unreachable")

    return findings


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


def generate_historical_chart(history: List[float]) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.plot(range(1, len(history) + 1), history, marker='o', color="#0F62FE")
    ax.set_title("Historical Score Trend")
    ax.set_ylim(0, 100)
    ax.set_xlabel("Period")
    ax.set_ylabel("Score")
    ax.grid(True, alpha=0.25)
    return _fig_to_buf()


def line_chart(points: List[Tuple[str, float]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    labels = [p[0] for p in points]
    values = [p[1] for p in points]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    ax.plot(labels, values, marker='o', color="#2F80ED")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=25, ha='right')
    return _fig_to_buf()


def bar_chart(items: List[Tuple[str, float]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    labels = [i[0] for i in items]
    values = [i[1] for i in items]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    ax.bar(labels, values, color="#27AE60")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=25, ha='right')
    return _fig_to_buf()


def pie_chart(parts: List[Tuple[str, float]], title: str = "") -> io.BytesIO:
    labels = [p[0] for p in parts]
    sizes = [p[1] for p in parts]
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
    ax.axis('equal')
    ax.set_title(title)
    return _fig_to_buf()


# =========================================================
# SCORE SYSTEM
# =========================================================

def calculate_scores(audit_data: Dict[str, Any]):
    scores: Dict[str, float] = {}
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
    prs = Presentation()
    slide_layout = prs.slide_layouts[1]

    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Executive Audit Summary"

    content = slide.placeholders[1]
    content.text = f"Overall Score: {audit_data.get('overall_score', 0)}"

    prs.save(file_path)


# =========================================================
# DOCUMENT UTILITIES (Header/Footer/TOC)
# =========================================================

class _DocWithTOC(SimpleDocTemplate):
    def __init__(self, *args, **kwargs):
        self._heading_styles = {"Heading1": 0, "Heading2": 1}
        super().__init__(*args, **kwargs)

    def afterFlowable(self, flowable):
        from reportlab.platypus import Paragraph
        if isinstance(flowable, Paragraph):
            style_name = getattr(flowable.style, 'name', '')
            if style_name in self._heading_styles:
                level = self._heading_styles[style_name]
                text = flowable.getPlainText()
                # make a bookmark
                key = f"h_{hash((text, self.page))}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
                # notify TOC
                self.notify('TOCEntry', (level, text, self.page))


def _draw_header_footer(c: canvas.Canvas, doc: SimpleDocTemplate, url: str, branding: Dict[str, Any]):
    c.saveState()

    # Header line
    c.setStrokeColor(colors.HexColor(branding.get("primary_color", "#2c3e50")))
    c.setLineWidth(0.6)
    c.line(doc.leftMargin, doc.height + doc.topMargin + 6, doc.width + doc.leftMargin, doc.height + doc.topMargin + 6)

    # Header text
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#525252"))
    header_left = f"{branding.get('company_name', 'WebAudit')} — {url or ''}"
    c.drawString(doc.leftMargin, doc.height + doc.topMargin + 10, header_left[:120])

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
# MAIN PDF GENERATOR (keeps the same inputs/outputs)
# =========================================================

def generate_audit_pdf(audit_data: Dict[str, Any],
                       client_config: Dict[str, Any] = None,
                       history_scores: List[float] = None) -> bytes:

    branding = get_branding(client_config or {})

    buffer = io.BytesIO()
    doc = _DocWithTOC(buffer, pagesize=A4,
                      leftMargin=36, rightMargin=36, topMargin=54, bottomMargin=54,
                      title="FF Tech Web Audit",
                      author=branding.get('company_name', 'WebAudit'))

    elements: List[Any] = []
    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        name="KPIHeader",
        parent=styles["Heading2"],
        textColor=colors.HexColor(branding.get("primary_color", "#2c3e50")),
    ))

    # =============== COVER PAGE ==================
    url = audit_data.get("url", "")
    tool_version = audit_data.get("tool_version", "v1.0")

    # Logo
    logo_path = branding.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        try:
            elements.append(Image(logo_path, width=1.6 * inch, height=1.6 * inch))
        except Exception:
            pass

    elements.append(Paragraph(branding["company_name"], styles["Title"]))
    elements.append(Spacer(1, 0.15 * inch))

    elements.append(Paragraph("FF Tech Web Audit Report", styles["Heading1"]))
    elements.append(Spacer(1, 0.1 * inch))

    elements.append(Paragraph(f"Website: {url}", styles["Normal"]))
    elements.append(Paragraph(f"Report Time (UTC): {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elements.append(Paragraph(f"Audit/Tool Version: {tool_version}", styles["Normal"]))
    elements.append(Spacer(1, 0.15 * inch))

    # QR code to dashboard or URL
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
            elements.append(Paragraph("Scan for online dashboard", styles["Caption"]) if "Caption" in styles else Spacer(1, 0.01))
        except Exception:
            pass

    elements.append(PageBreak())

    # =============== TABLE OF CONTENTS ===============
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(fontName='Helvetica-Bold', name='TOCHeading1', fontSize=12, leftIndent=20, firstLineIndent=-10, spaceBefore=6),
        ParagraphStyle(fontName='Helvetica', name='TOCHeading2', fontSize=10, leftIndent=36, firstLineIndent=-10, spaceBefore=2),
    ]
    elements.append(Paragraph("Table of Contents", styles["Heading1"]))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(toc)
    elements.append(PageBreak())

    # =============== EXECUTIVE SUMMARY ===============
    score_data = calculate_scores(audit_data)
    elements.append(Paragraph("Executive Summary", styles["Heading1"]))
    elements.append(Spacer(1, 0.08 * inch))
    elements.append(Paragraph(f"Overall Score: <b>{score_data['overall_score']}</b>", styles["Normal"]))

    # Category scores table
    cat = score_data["category_scores"]
    table_data = [["Category", "Score"]] + [[k.capitalize(), f"{cat[k]:.0f}"] for k in WEIGHTAGE]
    table = Table(table_data, colWidths=[2.5 * inch, 1.2 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#121619")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDE1E6")),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]))
    elements.append(table)
    elements.append(PageBreak())

    # =============== HISTORICAL TREND (Optional) ===============
    if history_scores:
        elements.append(Paragraph("Historical Performance", styles["Heading1"]))
        chart = generate_historical_chart(history_scores)
        elements.append(Image(chart, width=5.6 * inch, height=3.2 * inch))
        elements.append(PageBreak())

    # =============== SECURITY FINDINGS ===============
    elements.append(Paragraph("Security Findings", styles["Heading1"]))
    vulns = run_basic_vulnerability_scan(url)
    if vulns:
        for v in vulns:
            elements.append(Paragraph(f"- {v}", styles["Normal"]))
    else:
        elements.append(Paragraph("No findings detected by basic scan.", styles["Normal"]))

    # =============== OPTIONAL: TRAFFIC & SEARCH (if provided) ===============
    traffic = audit_data.get("traffic")  # expected dict with keys and time-series
    gsc = audit_data.get("gsc")  # expected dict

    if traffic and isinstance(traffic, dict):
        elements.append(PageBreak())
        elements.append(Paragraph("Traffic & Google Search Metrics", styles["Heading1"]))
        # Example visualizations if data is available
        try:
            if 'trend' in traffic:
                points = [(str(k), float(v)) for k, v in traffic['trend']]
                img = line_chart(points, title="Traffic Trend", xlabel="Period", ylabel="Visitors")
                elements.append(Image(img, width=5.6 * inch, height=3.2 * inch))
            if 'sources' in traffic:
                parts = [(k, float(v)) for k, v in traffic['sources'].items()]
                img = pie_chart(parts, title="Traffic Sources")
                elements.append(Image(img, width=4.8 * inch, height=4.8 * inch))
        except Exception:
            pass

    if gsc and isinstance(gsc, dict) and 'queries' in gsc:
        try:
            top_q = gsc.get('queries', [])[:10]
            items = [(q.get('query', ''), float(q.get('clicks', 0))) for q in top_q]
            img = bar_chart(items, title="Top Queries by Clicks", xlabel="Query", ylabel="Clicks")
            elements.append(Image(img, width=5.6 * inch, height=3.2 * inch))
        except Exception:
            pass

    # Build document with header/footer
    def _first_page(c, d):
        _draw_header_footer(c, d, url, branding)

    def _later_pages(c, d):
        _draw_header_footer(c, d, url, branding)

    doc.build(elements, onFirstPage=_first_page, onLaterPages=_later_pages)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # DIGITAL SIGNATURE (print to stdout/log)
    signature = generate_digital_signature(pdf_bytes)
    print("Digital Signature:", signature)

    # EXECUTIVE PPT (optional convenience)
    try:
        generate_executive_ppt({"overall_score": score_data['overall_score']}, "/tmp/executive_summary.pptx")
    except Exception:
        pass

    return pdf_bytes
