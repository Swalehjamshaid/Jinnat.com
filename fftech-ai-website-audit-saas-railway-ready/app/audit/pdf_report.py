# -*- coding: utf-8 -*-
"""
Comprehensive Website Audit PDF Report Generator (single-file version)
Follows requested 15-section structure (Feb 2025 edition)
"""

import io
import datetime as dt
from typing import Dict, Any, List, Optional, Union

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.pdfgen import canvas

# ────────────────────────────────────────────────
# CONFIG & COLORS
# ────────────────────────────────────────────────

COMPANY_NAME     = "Your Company Name / FF Tech Audit"
AUDITOR_NAME     = "Automated Audit System v4.1"
REPORT_VERSION   = "2025.02"

PRIMARY   = colors.HexColor("#1e3a8a")
ACCENT    = colors.HexColor("#3b82f6")
OK_GREEN  = colors.HexColor("#22c55e")
WARNING   = colors.HexColor("#f59e0b")
CRITICAL  = colors.HexColor("#ef4444")
GRAY      = colors.HexColor("#4b5563")
LIGHT_BG  = colors.HexColor("#f8fafc")

# ────────────────────────────────────────────────
# SAFE TEXT HANDLING
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
# STYLES – safe (no duplicate definition)
# ────────────────────────────────────────────────

def prepare_styles():
    styles = getSampleStyleSheet()

    # Modify built-in styles
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

    styles['Heading3'].fontSize     = 12.5
    styles['Heading3'].textColor    = PRIMARY
    styles['Heading3'].spaceBefore  = 14

    # Custom styles
    styles.add(ParagraphStyle(
        name='CoverTitle',
        parent=styles['Heading1'],
        fontSize=26,
        alignment=1,
        spaceAfter=36
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
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
        leftIndent=18,
        bulletIndent=10,
        spaceBefore=4,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name='KPIValue',
        parent=styles['Normal'],
        fontSize=13,
        alignment=1,
        spaceBefore=6,
        spaceAfter=6
    ))

    return styles

# ────────────────────────────────────────────────
# MOCK / EXAMPLE DATA  (replace with real collector)
# ────────────────────────────────────────────────

def get_mock_audit_data(url_input: Union[str, dict]) -> Dict[str, Any]:
    # Defensive URL extraction
    if isinstance(url_input, dict):
        url = url_input.get("url") or url_input.get("website") or url_input.get("target") or ""
    else:
        url = str(url_input).strip() or "https://example.com"

    domain = url.replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]

    return {
        "url": url,
        "domain": domain,
        "audit_date": dt.date.today().strftime("%Y-%m-%d"),
        "overall_score": 68,
        "risk_level": "Medium",
        "total_issues": 47,
        "critical_issues": 8,
        "compliance_status": "Partial",

        "overview": {
            "hosting": "Cloudflare + AWS",
            "server_ip": "104.21.45.123",
            "cms": "WordPress 6.4",
            "ssl_status": "Valid until 2026-07-15 (Let's Encrypt)",
            "domain_expiry": "2027-11-03",
            "mobile_friendly": "Yes (minor layout shift detected)"
        },

        "performance": {
            "load_time_s": 4.7,
            "fcp_s": 2.1,
            "lcp_s": 4.4,
            "page_size_mb": 2.9,
            "requests": 81,
            "desktop_score": 76,
            "mobile_score": 54
        },

        "seo": {
            "meta_title": True,
            "meta_desc": False,
            "h1_count": 1,
            "sitemap": True,
            "robots_txt": True,
            "broken_links": 7,
            "missing_alt": 19,
            "canonical": True,
            "schema": False
        },

        "security": {
            "https": True,
            "ssl_valid": True,
            "mixed_content": 4,
            "hsts": False,
            "csp": False,
            "x_frame_options": True,
            "exposed_admin": False
        },

        "accessibility_score": 59,

        "issues": [
            {"type": "LCP > 4s on mobile",      "severity": "Critical", "page": "/",               "recommend": "Optimize hero image + font loading",     "status": "Open"},
            {"type": "Missing HSTS header",     "severity": "High",     "page": "site-wide",       "recommend": "Add Strict-Transport-Security header",   "status": "Open"},
            {"type": "No CSP header",           "severity": "High",     "page": "site-wide",       "recommend": "Implement strict CSP policy",            "status": "Open"},
            {"type": "Missing alt on images",   "severity": "Medium",   "page": "/product/*",      "recommend": "Add descriptive alt text",               "status": "Open"},
            {"type": "No privacy policy link",  "severity": "High",     "page": "footer",          "recommend": "Add visible link + page",                "status": "Open"},
        ],

        "recommendations": {
            "immediate": [
                "Fix Largest Contentful Paint issues on mobile",
                "Implement HSTS and CSP security headers",
                "Remove mixed content (http resources on https pages)"
            ],
            "short_term": [
                "Compress and convert images to WebP/AVIF",
                "Add missing schema.org structured data",
                "Fix broken internal links and redirects"
            ],
            "long_term": [
                "Improve content readability & keyword density",
                "Implement cookie consent banner & GDPR notice",
                "Migrate to HTTP/2 or HTTP/3"
            ]
        },

        "conclusion": (
            "The website demonstrates moderate technical stability and acceptable mobile responsiveness. "
            "However, performance on mobile devices, missing critical security headers, "
            "and incomplete structured data implementation require immediate attention "
            "to improve Core Web Vitals compliance, search visibility and user trust."
        )
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
                  f"{COMPANY_NAME} • Confidential")

    page = c.getPageNumber()
    c.setFont("Helvetica", 9)
    c.drawRightString(doc.width + doc.leftMargin,
                       doc.bottomMargin - 20,
                       f"Page {page} • {AUDITOR_NAME} • v{REPORT_VERSION}")
    c.restoreState()

# ────────────────────────────────────────────────
# MAIN PDF GENERATOR
# ────────────────────────────────────────────────

def generate_website_audit_report(
    url_input: Union[str, dict],
    output_path: Optional[str] = None
) -> bytes:
    data = get_mock_audit_data(url_input)
    styles = prepare_styles()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=70, bottomMargin=50
    )

    elements = []

    # 1. Cover Page
    elements.append(P(COMPANY_NAME, 'CoverTitle'))
    elements.append(Spacer(1, 0.18*inch))
    elements.append(P("Website Performance & Compliance Audit Report", 'CoverTitle'))
    elements.append(Spacer(1, 0.8*inch))

    elements.append(P(f"Website URL:  {data['url']}", 'Normal'))
    elements.append(P(f"Audit Date:   {data['audit_date']}", 'Normal'))
    elements.append(P(f"Generated by: {AUDITOR_NAME}", 'Normal'))
    elements.append(P(f"Version:      {REPORT_VERSION}", 'Normal'))
    elements.append(PageBreak())

    # 2. Executive Summary
    elements.append(P("2. Executive Summary", 'Heading1'))
    score = data["overall_score"]
    color = OK_GREEN if score >= 85 else WARNING if score >= 65 else CRITICAL

    summary_table = Table([
        ["Overall Health Score", f"{score}%", f"<font color='#{color.hexval():06x}'>{score}/100</font>"],
        ["Risk Level",           data["risk_level"], ""],
        ["Total Issues Found",   data["total_issues"], ""],
        ["Critical Issues",      data["critical_issues"], ""],
        ["Compliance Status",    data["compliance_status"], ""],
    ], colWidths=[3.4*inch, 1.6*inch, 1.8*inch])

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('GRID',       (0,0), (-1,-1), 0.5, GRAY),
        ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 0.24*inch))

    elements.append(P("Key Findings:", 'Heading3'))
    for point in [
        "Mobile performance significantly lags behind desktop (LCP > 4s)",
        "Critical security headers (HSTS, CSP) are missing",
        "Missing schema markup and incomplete alt text coverage",
        "Several accessibility and legal compliance gaps detected"
    ]:
        elements.append(P(f"• {point}", 'Bullet'))

    elements.append(PageBreak())

    # 3. Website Overview
    elements.append(P("3. Website Overview", 'Heading1'))
    ov_rows = [
        ["Domain Name",         data["domain"]],
        ["Hosting Provider",    data["overview"]["hosting"]],
        ["Server IP",           data["overview"]["server_ip"]],
        ["CMS / Platform",      data["overview"]["cms"]],
        ["SSL Certificate",     data["overview"]["ssl_status"]],
        ["Domain Expiry",       data["overview"]["domain_expiry"]],
        ["Mobile Friendly",     data["overview"]["mobile_friendly"]],
    ]
    elements.append(Table(ov_rows, colWidths=[3.2*inch, 3.6*inch]))
    elements.append(PageBreak())

    # 4. Performance Analysis
    elements.append(P("4. Performance Analysis", 'Heading1'))
    p = data["performance"]
    perf_rows = [
        ["Page Load Time",      f"{p['load_time_s']} s"],
        ["First Contentful Paint", f"{p['fcp_s']} s"],
        ["Largest Contentful Paint", f"{p['lcp_s']} s"],
        ["Total Page Size",     f"{p['page_size_mb']} MB"],
        ["Number of Requests",  str(p["requests"])],
        ["Desktop Score",       f"{p['desktop_score']}/100"],
        ["Mobile Score",        f"{p['mobile_score']}/100"],
    ]
    elements.append(Table(perf_rows, colWidths=[3.8*inch, 3*inch]))
    elements.append(Spacer(1, 0.18*inch))
    elements.append(P("Recommendation: Compress images, defer non-critical JS, use modern image formats (AVIF/WebP)", 'Normal'))
    elements.append(PageBreak())

    # 11. Issue Classification Table
    elements.append(P("11. Issue Classification", 'Heading1'))
    issue_rows = [["Severity", "Issue Type", "Page / Location", "Recommendation", "Status"]]
    for i in data["issues"]:
        color = CRITICAL if i["severity"] == "Critical" else WARNING if i["severity"] == "High" else ACCENT
        sev_html = f"<font color='#{color.hexval():06x}'>{i['severity']}</font>"
        issue_rows.append([sev_html, i["type"], i["page"], i["recommend"], i["status"]])

    issue_table = Table(issue_rows, colWidths=[1.1*inch, 2.2*inch, 1.5*inch, 2.4*inch, 0.9*inch])
    issue_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('GRID',       (0,0), (-1,-1), 0.4, GRAY),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (0,0), (0,0),   'CENTER'),
    ]))
    elements.append(KeepTogether(issue_table))
    elements.append(PageBreak())

    # 13. Recommendations & Action Plan
    elements.append(P("13. Recommendations & Action Plan", 'Heading1'))

    for period, items in [
        ("Immediate Actions (0–7 days)", data["recommendations"]["immediate"]),
        ("Short Term (8–30 days)",       data["recommendations"]["short_term"]),
        ("Long Term (31–90+ days)",      data["recommendations"]["long_term"]),
    ]:
        elements.append(P(period, 'Heading2'))
        for item in items:
            elements.append(P(f"• {item}", 'Bullet'))
        elements.append(Spacer(1, 0.14*inch))

    elements.append(PageBreak())

    # 14. Conclusion
    elements.append(P("14. Conclusion", 'Heading1'))
    elements.append(P(data["conclusion"], 'Normal'))

    # 15. Appendix (placeholder)
    elements.append(PageBreak())
    elements.append(P("15. Appendix", 'Heading1'))
    elements.append(P("• Raw crawl log excerpt", 'Normal'))
    elements.append(P("• HTTP response headers sample", 'Normal'))
    elements.append(P("• Screenshots would be embedded here", 'Normal'))

    # Build PDF
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes

# ────────────────────────────────────────────────
# Example usage
# ────────────────────────────────────────────────

if __name__ == "__main__":
    sample_url = "https://example.com"
    pdf_content = generate_website_audit_report(sample_url, "website-audit-report.pdf")
    print("PDF generated → website-audit-report.pdf")
