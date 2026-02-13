# -*- coding: utf-8 -*-
"""
Comprehensive single-file website audit PDF report generator
Last major fixes: Feb 2025 style duplication + url handling
"""

import io
import datetime as dt
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlparse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)
from reportlab.pdfgen import canvas

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────

COMPANY = "FF Tech Audit"
VERSION = "2025.02"
PRIMARY = colors.HexColor("#1e40af")
ACCENT  = colors.HexColor("#3b82f6")
OK      = colors.HexColor("#16a34a")
WARN    = colors.HexColor("#ca8a04")
CRIT    = colors.HexColor("#dc2626")
GRAY    = colors.gray

# ────────────────────────────────────────────────
# SAFE TEXT
# ────────────────────────────────────────────────

def safe_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s

def P(text, style="Normal", bullet=None):
    return Paragraph(safe_text(text), style, bulletText=bullet)

# ────────────────────────────────────────────────
# STYLES – safe version (never redefines built-in names)
# ────────────────────────────────────────────────

def prepare_styles():
    styles = getSampleStyleSheet()

    # Modify existing built-in styles
    styles['Normal'].fontSize   = 10.5
    styles['Normal'].leading    = 14
    styles['Normal'].spaceAfter = 8

    styles['Heading1'].fontSize     = 18
    styles['Heading1'].textColor    = PRIMARY
    styles['Heading1'].spaceBefore  = 24
    styles['Heading1'].spaceAfter   = 12

    styles['Heading2'].fontSize     = 14
    styles['Heading2'].textColor    = ACCENT
    styles['Heading2'].spaceBefore  = 18
    styles['Heading2'].spaceAfter   = 8

    # Add only NEW style names
    styles.add(ParagraphStyle(
        name='TitleBig',
        parent=styles['Heading1'],
        fontSize=24,
        alignment=1,
        spaceAfter=36
    ))

    styles.add(ParagraphStyle(
        name='Section',
        parent=styles['Heading2'],
        spaceBefore=20,
        spaceAfter=10
    ))

    styles.add(ParagraphStyle(
        name='Caption',
        parent=styles['Normal'],
        fontSize=9,
        textColor=GRAY,
        alignment=1,
        spaceBefore=4,
        spaceAfter=10
    ))

    styles.add(ParagraphStyle(
        name='Bullet',
        parent=styles['Normal'],
        leftIndent=16,
        bulletIndent=8,
        spaceBefore=4,
        spaceAfter=4
    ))

    return styles

# ────────────────────────────────────────────────
# MOCK AUDIT DATA (replace with your real data collector)
# ────────────────────────────────────────────────

def get_audit_data(input_url: Union[str, dict]) -> Dict[str, Any]:
    # Defensive URL normalization
    if isinstance(input_url, dict):
        url = (
            input_url.get("url") or
            input_url.get("website") or
            input_url.get("target") or
            input_url.get("link") or
            ""
        )
    else:
        url = str(input_url).strip()

    if not url:
        url = "https://example.com"

    parsed = urlparse(url)
    domain = parsed.netloc or parsed.hostname or url.split("://", 1)[-1].split("/", 1)[0]

    return {
        "url": url,
        "domain": domain,
        "audit_date": dt.date.today().strftime("%Y-%m-%d"),
        "overall_score": 73,
        "risk": "Medium",
        "total_issues": 38,
        "critical": 6,
        "overview": {
            "hosting": "Cloudflare + Vercel",
            "cms": "Next.js",
            "ssl": "Valid (Let's Encrypt)",
        },
        "performance": {
            "lcp": 3.8,
            "desktop": 81,
            "mobile": 62
        },
        "issues": [
            {"sev": "Critical", "desc": "LCP > 3.5s on mobile", "page": "/"},
            {"sev": "High",     "desc": "Missing HSTS",         "page": "site-wide"},
            {"sev": "Medium",   "desc": "Missing alt text",     "page": "/product/*"},
        ],
        "rec_immediate": ["Fix LCP", "Add HSTS"],
        "rec_short":     ["Optimize images", "Add schema"],
        "rec_long":      ["Modernize stack", "Improve content"],
        "conclusion": "Good foundation — performance and security headers need priority attention."
    }

# ────────────────────────────────────────────────
# HEADER / FOOTER
# ────────────────────────────────────────────────

def draw_header_footer(c: canvas.Canvas, doc):
    c.saveState()
    c.setStrokeColor(PRIMARY)
    c.setLineWidth(0.5)
    c.line(doc.leftMargin-10, doc.height + doc.topMargin + 12,
           doc.width + doc.leftMargin + 10, doc.height + doc.topMargin + 12)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GRAY)
    c.drawString(doc.leftMargin, doc.height + doc.topMargin + 18,
                  f"{COMPANY} • Confidential Audit")

    page = c.getPageNumber()
    c.setFont("Helvetica", 9)
    c.drawRightString(doc.width + doc.leftMargin,
                       doc.bottomMargin - 20,
                       f"Page {page} • v{VERSION}")
    c.restoreState()

# ────────────────────────────────────────────────
# MAIN PDF GENERATOR
# ────────────────────────────────────────────────

def generate_audit_pdf(url_input: Union[str, dict], output_path: Optional[str] = None) -> bytes:
    data = get_audit_data(url_input)
    styles = prepare_styles()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=70, bottomMargin=50
    )

    elements = []

    # Cover
    elements.append(P(f"{COMPANY}\nWebsite Audit Report", 'TitleBig'))
    elements.append(Spacer(1, 0.6*inch))
    elements.append(P(f"Website: {data['url']}", 'Normal'))
    elements.append(P(f"Audit Date: {data['audit_date']}", 'Normal'))
    elements.append(P(f"Version: {VERSION}", 'Normal'))
    elements.append(PageBreak())

    # Executive Summary
    elements.append(P("Executive Summary", 'Heading1'))
    score_color = OK if data['overall_score'] >= 85 else WARN if data['overall_score'] >= 65 else CRIT
    rows = [
        ["Overall Score", f"{data['overall_score']}%", f"<font color='#{score_color.hexval():06x}'>{data['overall_score']}/100</font>"],
        ["Risk Level",    data['risk'], ""],
        ["Total Issues",  data['total_issues'], ""],
        ["Critical",      data['critical'], ""],
    ]
    t = Table(rows, colWidths=[3*inch, 1.8*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.3*inch))
    elements.append(PageBreak())

    # Overview
    elements.append(P("Website Overview", 'Section'))
    ov = [
        ["Domain",   data["domain"]],
        ["Hosting",  data["overview"]["hosting"]],
        ["CMS",      data["overview"]["cms"]],
        ["SSL",      data["overview"]["ssl"]],
    ]
    elements.append(Table(ov, colWidths=[2.8*inch, 4*inch]))
    elements.append(PageBreak())

    # Issues
    elements.append(P("Key Issues", 'Section'))
    issue_rows = [["Severity", "Description", "Location"]]
    for i in data["issues"]:
        color = CRIT if i["sev"] == "Critical" else WARN
        issue_rows.append([
            f"<font color='#{color.hexval():06x}'>{i['sev']}</font>",
            i["desc"],
            i["page"]
        ])
    it = Table(issue_rows, colWidths=[1.4*inch, 3.2*inch, 2.2*inch])
    it.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
        ('GRID', (0,0), (-1,-1), 0.4, colors.black),
    ]))
    elements.append(it)
    elements.append(PageBreak())

    # Recommendations
    elements.append(P("Action Plan", 'Section'))
    for title, items in [
        ("Immediate (0–7 days)", data["rec_immediate"]),
        ("Short-term (8–30 days)", data["rec_short"]),
        ("Long-term (31+ days)", data["rec_long"]),
    ]:
        elements.append(P(title, 'Heading2'))
        for item in items:
            elements.append(P(f"• {item}", 'Bullet'))
        elements.append(Spacer(1, 0.12*inch))

    elements.append(PageBreak())

    # Conclusion
    elements.append(P("Conclusion", 'Section'))
    elements.append(P(data["conclusion"], 'Normal'))

    # Build
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes

# ────────────────────────────────────────────────
# Quick test
# ────────────────────────────────────────────────

if __name__ == "__main__":
    test_url = "https://www.apple.com"
    # test_url = {"url": "https://example.com", "client": "Test Co"}   # dict test
    generate_audit_pdf(test_url, "audit-report.pdf")
    print("PDF written to audit-report.pdf")
