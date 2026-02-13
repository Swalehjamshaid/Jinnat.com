# -*- coding: utf-8 -*-
"""
Comprehensive Website Audit PDF Report Generator (single file)
Enterprise style - CEO / C-level readable
Last major update concept: 2025
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
    PageBreak, Image, KeepTogether
)
from reportlab.pdfgen import canvas

# ────────────────────────────────────────────────
# CONFIG & BRANDING
# ────────────────────────────────────────────────

COMPANY_NAME    = "FF Tech Security & Performance Audit"
BRAND_COLOR     = colors.HexColor("#1e40af")      # deep blue
ACCENT_COLOR    = colors.HexColor("#3b82f6")
OK_COLOR        = colors.HexColor("#16a34a")
WARN_COLOR      = colors.HexColor("#ca8a04")
CRITICAL_COLOR  = colors.HexColor("#dc2626")
GRAY            = colors.HexColor("#4b5563")
LIGHT_BG        = colors.HexColor("#f8fafc")

VERSION         = "2025.04"
AUDITOR         = "Automated Audit Engine"

# ────────────────────────────────────────────────
# SAFE TEXT & PARAGRAPH HELPER
# ────────────────────────────────────────────────

def safe_text(text: Any) -> str:
    if text is None:
        return ""
    return str(text).replace("<", "&lt;").replace(">", "&gt;")

def P(text, style_name="Normal", bullet=None):
    return Paragraph(safe_text(text), style_name, bulletText=bullet)

# ────────────────────────────────────────────────
# HEADER / FOOTER
# ────────────────────────────────────────────────

def draw_header_footer(c: canvas.Canvas, doc):
    c.saveState()
    c.setStrokeColor(BRAND_COLOR)
    c.setLineWidth(0.5)
    c.line(doc.leftMargin - 10, doc.topMargin + doc.height + 12,
           doc.width + doc.leftMargin + 10, doc.topMargin + doc.height + 12)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GRAY)
    c.drawString(doc.leftMargin, doc.topMargin + doc.height + 18,
                  f"{COMPANY_NAME} • Confidential")

    page_num = c.getPageNumber()
    c.setFont("Helvetica", 9)
    c.drawRightString(doc.width + doc.leftMargin,
                       doc.bottomMargin - 20,
                       f"Page {page_num} • v{VERSION} • {dt.date.today().strftime('%Y-%m')}")
    c.restoreState()

# ────────────────────────────────────────────────
# STYLES – safe version (no duplicate keys)
# ────────────────────────────────────────────────

def prepare_styles():
    styles = getSampleStyleSheet()

    # Modify built-in styles instead of adding duplicates
    styles['Normal'].fontSize   = 10.5
    styles['Normal'].leading    = 14
    styles['Normal'].spaceAfter = 8

    styles['Heading1'].fontSize     = 18
    styles['Heading1'].textColor    = BRAND_COLOR
    styles['Heading1'].spaceBefore  = 24
    styles['Heading1'].spaceAfter   = 12

    styles['Heading2'].fontSize     = 14
    styles['Heading2'].textColor    = ACCENT_COLOR
    styles['Heading2'].spaceBefore  = 18
    styles['Heading2'].spaceAfter   = 8

    styles['Heading3'].fontSize     = 12
    styles['Heading3'].textColor    = BRAND_COLOR
    styles['Heading3'].spaceBefore  = 14

    # Custom styles (new names → no conflict)
    styles.add(ParagraphStyle(
        name='Caption',
        parent=styles['Normal'],
        fontSize=9,
        textColor=GRAY,
        alignment=1,
        spaceBefore=4, spaceAfter=10
    ))

    styles.add(ParagraphStyle(
        name='KPIValue',
        parent=styles['Normal'],
        fontSize=13,
        alignment=1,
        spaceBefore=6, spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        name='Bullet',
        parent=styles['Normal'],
        leftIndent=16,
        bulletIndent=8,
        bulletFontName='Symbol',
        spaceBefore=4, spaceAfter=4
    ))

    return styles

# ────────────────────────────────────────────────
# EXAMPLE / MOCK DATA (replace with real audit results)
# ────────────────────────────────────────────────

def get_sample_audit_data(url: str) -> Dict[str, Any]:
    domain = url.replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]

    return {
        "url": url,
        "domain": domain,
        "audit_date": dt.date.today().strftime("%Y-%m-%d"),
        "overall_score": 71,
        "risk_level": "Medium",
        "total_issues": 42,
        "critical_count": 7,
        "compliance": "Partial",

        "overview": {
            "hosting": "Cloudflare + Vercel",
            "ip": "104.18.26.123",
            "cms": "Next.js / React",
            "ssl": "Valid until 2026-07-15 (Let's Encrypt)",
            "expiry": "2027-11-03",
            "mobile": "Responsive (but layout shift detected)",
        },

        "performance": {
            "load_time": 4.1,
            "fcp": 1.9,
            "lcp": 4.2,
            "cls": 0.18,
            "page_size_mb": 2.4,
            "requests": 72,
            "desktop": 78,
            "mobile": 59,
        },

        "seo": {
            "title": True,
            "meta_desc": False,
            "h1": 1,
            "h2": 8,
            "sitemap": True,
            "robots": True,
            "broken": 5,
            "alt_missing": 12,
            "canonical": True,
            "schema": False,
        },

        "security": {
            "https": True,
            "hsts": False,
            "csp": False,
            "xfo": True,
            "mixed_content": 2,
        },

        "accessibility": 64,

        "issues": [
            {"sev": "Critical", "type": "LCP > 4s on mobile",      "page": "/product/*",   "fix": "Optimize hero images + font loading"},
            {"sev": "High",     "type": "Missing HSTS header",      "page": "site-wide",    "fix": "Implement Strict-Transport-Security"},
            {"sev": "High",     "type": "No CSP header",            "page": "site-wide",    "fix": "Add strict Content-Security-Policy"},
            {"sev": "Medium",   "type": "Missing alt on images",    "page": "/",            "fix": "Add descriptive alt attributes"},
            {"sev": "Medium",   "type": "No privacy policy link",   "page": "footer",       "fix": "Add visible link in footer"},
            # ... more in production
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
                "Migrate to modern image formats site-wide",
                "Improve content readability & keyword density",
                "Implement cookie consent & GDPR notice"
            ]
        },

        "conclusion": (
            "The website shows good structural foundations and mobile responsiveness. "
            "However, performance on mobile devices, several missing security headers "
            "and incomplete structured data implementation require priority attention "
            "to improve search visibility, Core Web Vitals compliance and user trust."
        )
    }

# ────────────────────────────────────────────────
# PDF GENERATION MAIN FUNCTION
# ────────────────────────────────────────────────

def generate_comprehensive_audit_pdf(
    url_input: Union[str, dict],
    output_filename: Optional[str] = None
) -> bytes:
    # Normalize URL input
    if isinstance(url_input, dict):
        url = url_input.get("url") or url_input.get("website") or ""
    else:
        url = str(url_input).strip()

    if not url:
        raise ValueError("No valid URL provided")

    data = get_sample_audit_data(url)

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=70, bottomMargin=50,
        title="Website Audit Report",
        author=COMPANY_NAME
    )

    styles = prepare_styles()
    elements: List[Any] = []

    # ── 1. Cover Page ───────────────────────────────────────
    elements.append(P(COMPANY_NAME, 'Heading1'))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(P("Website Performance, SEO & Security Audit Report", 'Heading1'))
    elements.append(Spacer(1, 0.6*inch))

    elements.append(P(f"Website: {data['url']}", 'Normal'))
    elements.append(P(f"Audit Date: {data['audit_date']}", 'Normal'))
    elements.append(P(f"Prepared by: {AUDITOR}", 'Normal'))
    elements.append(P(f"Report Version: {VERSION}", 'Normal'))

    elements.append(Spacer(1, 1.2*inch))
    elements.append(P("Confidential – For Internal Use Only", 'Caption'))
    elements.append(PageBreak())

    # ── 2. Executive Summary ────────────────────────────────
    elements.append(P("Executive Summary", 'Heading1'))
    elements.append(Spacer(1, 0.12*inch))

    score = data["overall_score"]
    risk_color = OK_COLOR if score >= 85 else WARN_COLOR if score >= 65 else CRITICAL_COLOR

    summary_table = Table([
        ["Overall Health Score", f"{score}%", f"<font color='#{risk_color.hexval():06x}'>{score}/100</font>"],
        ["Risk Level",           data["risk_level"], ""],
        ["Total Issues",         data["total_issues"], ""],
        ["Critical Issues",      data["critical_count"], ""],
        ["Compliance Status",    data["compliance"], ""],
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

    elements.append(P("Key Observations:", 'Heading3'))
    for point in [
        "Mobile performance significantly lags behind desktop",
        "Important security headers (HSTS, CSP) are missing",
        "Structured data implementation is incomplete",
        "Several accessibility and SEO quick-wins available"
    ]:
        elements.append(P(f"• {point}", 'Bullet'))

    elements.append(PageBreak())

    # ── 3. Website & Infrastructure Overview ────────────────
    elements.append(P("Website & Infrastructure Overview", 'Heading1'))
    overview_data = [
        ["Domain",              data["domain"]],
        ["Hosting / CDN",       data["overview"]["hosting"]],
        ["Server IP",           data["overview"]["ip"]],
        ["Platform / CMS",      data["overview"]["cms"]],
        ["SSL Certificate",     data["overview"]["ssl"]],
        ["Domain Expiry",       data["overview"]["expiry"]],
        ["Mobile Responsiveness", data["overview"]["mobile"]],
    ]
    elements.append(Table(overview_data, colWidths=[3*inch, 4*inch]))
    elements.append(PageBreak())

    # ── 4. Performance Analysis ─────────────────────────────
    elements.append(P("Performance Analysis", 'Heading1'))
    p = data["performance"]
    perf_rows = [
        ["Page Load Time",      f"{p['load_time']} s"],
        ["First Contentful Paint", f"{p['fcp']} s"],
        ["Largest Contentful Paint", f"{p['lcp']} s"],
        ["Cumulative Layout Shift", f"{p['cls']}"],
        ["Total Page Size",     f"{p['page_size_mb']} MB"],
        ["Number of Requests",  str(p["requests"])],
        ["Desktop Score",       f"{p['desktop']}/100"],
        ["Mobile Score",        f"{p['mobile']}/100"],
    ]
    elements.append(Table(perf_rows, colWidths=[3.8*inch, 3*inch]))
    elements.append(Spacer(1, 0.18*inch))
    elements.append(P("Priority: Improve LCP and CLS for better mobile user experience", 'Normal'))
    elements.append(PageBreak())

    # ── 11. Classified Issues Table ─────────────────────────
    elements.append(P("Classified Issues", 'Heading1'))
    issue_rows = [["Severity", "Issue", "Location", "Recommended Action"]]
    for issue in data["issues"]:
        color = CRITICAL_COLOR if issue["sev"] == "Critical" else WARN_COLOR if issue["sev"] == "High" else ACCENT_COLOR
        sev_text = f"<font color='#{color.hexval():06x}'>{issue['sev']}</font>"
        issue_rows.append([sev_text, issue["type"], issue["page"], issue["fix"]])

    issues_table = Table(issue_rows, colWidths=[1.3*inch, 2.4*inch, 1.5*inch, 2.6*inch])
    issues_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_BG),
        ('GRID',       (0,0), (-1,-1), 0.4, GRAY),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (0,0), (0,0),   'CENTER'),
    ]))
    elements.append(issues_table)
    elements.append(PageBreak())

    # ── 13. Recommendations & Action Plan ───────────────────
    elements.append(P("Recommendations & Action Plan", 'Heading1'))

    for title, items in [
        ("Immediate Actions (0–7 days)",    data["recommendations"]["immediate"]),
        ("Short-term (8–30 days)",          data["recommendations"]["short_term"]),
        ("Long-term (31–90+ days)",         data["recommendations"]["long_term"]),
    ]:
        elements.append(P(title, 'Heading2'))
        for item in items:
            elements.append(P(f"• {item}", 'Bullet'))
        elements.append(Spacer(1, 0.12*inch))

    elements.append(PageBreak())

    # ── 14. Conclusion ──────────────────────────────────────
    elements.append(P("Conclusion", 'Heading1'))
    elements.append(P(data["conclusion"], 'Normal'))

    # Build PDF
    doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    if output_filename:
        with open(output_filename, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes

# ────────────────────────────────────────────────
# CLI / Quick Test
# ────────────────────────────────────────────────

if __name__ == "__main__":
    sample_url = "https://www.apple.com"
    generate_comprehensive_audit_pdf(sample_url, "website-audit-report.pdf")
    print("PDF report generated → website-audit-report.pdf")
