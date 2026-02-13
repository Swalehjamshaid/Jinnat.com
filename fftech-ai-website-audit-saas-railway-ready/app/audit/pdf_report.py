# -*- coding: utf-8 -*-
"""
Website Audit PDF Report Generator (CEO-level)
Based on your 15-section specification - 2026 edition
"""

import io
import datetime as dt
from typing import Dict, List, Any, Optional

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
    PageBreak,
    Image,
    KeepInFrame,
)
from reportlab.pdfgen import canvas

# ────────────────────────────────────────────────
# CONFIG & STYLING
# ────────────────────────────────────────────────

COMPANY_NAME = "Your Company / FF Tech Audit"
AUDITOR_NAME = "AI Audit Engine v4.2"
VERSION = "2026.02"

PRIMARY = colors.HexColor("#1e3a8a")      # dark blue
ACCENT  = colors.HexColor("#3b82f6")      # bright blue
OK      = colors.HexColor("#22c55e")
WARN    = colors.HexColor("#f59e0b")
CRIT    = colors.HexColor("#ef4444")
GRAY    = colors.gray

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='CoverTitle',   fontSize=28, leading=34, textColor=PRIMARY, spaceAfter=18, alignment=1))
styles.add(ParagraphStyle(name='Section',      fontSize=18, textColor=PRIMARY, spaceBefore=24, spaceAfter=12))
styles.add(ParagraphStyle(name='SubSection',   fontSize=14, textColor=ACCENT,  spaceBefore=16, spaceAfter=8))
styles.add(ParagraphStyle(name='Normal',       fontSize=10, leading=12))
styles.add(ParagraphStyle(name='Small',        fontSize=9,  leading=11, textColor=colors.gray))
styles.add(ParagraphStyle(name='Bullet',       fontSize=10, leftIndent=14, bulletIndent=6, spaceBefore=4))

def P(txt, sty, **kw):
    return Paragraph(txt, styles[sty], **kw)

def emoji_severity(level: str) -> str:
    return {
        "Critical": "🔴",
        "High":     "🟠",
        "Medium":   "🟡",
        "Low":      "🟢",
    }.get(level, "⚪")

# ────────────────────────────────────────────────
# FAKE / PLACEHOLDER DATA  →  replace with real audit results
# ────────────────────────────────────────────────

def get_audit_data(url: str) -> Dict[str, Any]:
    # In real code: run crawling, Lighthouse API, whois, headers check, axe-core, etc.
    return {
        "url": url,
        "domain": url.replace("https://", "").split("/")[0],
        "audit_date": dt.date.today().strftime("%Y-%m-%d"),
        "overall_score": 68,
        "risk_level": "Medium",
        "total_issues": 47,
        "critical_issues": 6,
        "compliance_status": "Partial",

        "hosting": "Cloudflare + AWS (guessed from headers)",
        "ip": "104.21.45.123",
        "cms": "WordPress 6.4 (meta generator + wp-emoji)",
        "ssl_valid": "Yes (Let's Encrypt, valid until 2026-05-12)",
        "domain_expiry": "2027-03-19",
        "mobile_friendly": "Yes (responsive, but viewport issues)",

        "perf": {
            "load_time_s": 4.2,
            "fcp": 1.8,
            "lcp": 3.9,
            "page_size_mb": 2.7,
            "requests": 68,
            "desktop_score": 74,
            "mobile_score": 52,
        },

        "seo": {
            "meta_title": True,
            "meta_desc": False,
            "h1_count": 1,
            "sitemap": True,
            "robots_txt": True,
            "broken_links": 8,
            "missing_alt": 14,
            "canonical": True,
            "schema": False,
        },

        "security": {
            "https": True,
            "hsts": False,
            "csp": False,
            "xfo": True,
            "mixed_content": 3,
        },

        "a11y_score": 61,
        "issues": [
            {"type": "Missing HSTS header",            "severity": "High",    "page": "/",               "recommend": "Add Strict-Transport-Security header"},
            {"type": "LCP > 4s on mobile",              "severity": "Critical","page": "/product/xyz",   "recommend": "Optimize hero image + font loading"},
            {"type": "Missing alt on logo",             "severity": "Medium",  "page": "/",               "recommend": "Add meaningful alt text"},
            {"type": "No privacy policy link",          "severity": "High",    "page": "site-wide",       "recommend": "Add footer link + page"},
            # ... add 20–40 more in real implementation
        ],

        "recommendations": {
            "immediate": ["Fix critical LCP issues", "Add HSTS & CSP headers", "Remove mixed content"],
            "short": ["Optimize images & fonts", "Implement missing schema", "Fix broken links"],
            "long": ["Migrate to HTTP/2 or 3", "Improve content readability", "Add cookie consent banner"],
        },

        "conclusion": (
            "The website demonstrates acceptable baseline stability and mobile responsiveness. "
            "However, performance on mobile devices, several important security headers, "
            "and structured data implementation require immediate attention to improve "
            "SEO visibility, user trust and Core Web Vitals compliance."
        ),
    }

# ────────────────────────────────────────────────
# HEADER / FOOTER
# ────────────────────────────────────────────────

def draw_header_footer(canvas: canvas.Canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(PRIMARY)
    canvas.setLineWidth(0.4)
    canvas.line(doc.leftMargin, doc.height + doc.topMargin + 6,
                doc.width + doc.leftMargin, doc.height + doc.topMargin + 6)

    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(GRAY)
    canvas.drawString(doc.leftMargin, doc.height + doc.topMargin + 10,
                       f"{COMPANY_NAME} • Confidential Audit Report")

    canvas.setFont("Helvetica", 8)
    page = canvas.getPageNumber()
    canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 18,
                           f"Page {page} • {AUDITOR_NAME} • v{VERSION}")
    canvas.restoreState()

# ────────────────────────────────────────────────
# MAIN PDF BUILDER
# ────────────────────────────────────────────────

def generate_website_audit_pdf(url: str, output_path: Optional[str] = None) -> bytes:
    data = get_audit_data(url)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.9*inch, rightMargin=0.9*inch,
        topMargin=1.1*inch, bottomMargin=0.8*inch
    )

    elements = []

    # 1. Cover Page
    elements.append(P(COMPANY_NAME, "CoverTitle"))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(P("Website Performance & Compliance Audit Report", "CoverTitle"))
    elements.append(Spacer(1, 0.5*inch))

    elements.append(P(f"Website: {data['url']}", "Normal"))
    elements.append(P(f"Audit Date: {data['audit_date']}", "Normal"))
    elements.append(P(f"Generated by: {AUDITOR_NAME}", "Normal"))
    elements.append(P(f"Version: {VERSION}", "Normal"))
    elements.append(PageBreak())

    # 2. Executive Summary
    elements.append(P("Executive Summary", "Section"))
    elements.append(Spacer(1, 0.12*inch))

    score = data["overall_score"]
    risk = data["risk_level"]
    color = OK if score >= 85 else WARN if score >= 60 else CRIT

    rows = [
        ["Overall Health Score", f"{score}%", f"<font color='{color.hexval()}'>{score}/100</font>"],
        ["Risk Level", risk, ""],
        ["Total Issues Found", data["total_issues"], ""],
        ["Critical Issues", data["critical_issues"], ""],
        ["Compliance Status", data["compliance_status"], ""],
    ]
    t = Table(rows, colWidths=[3.2*inch, 1.8*inch, 1.8*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.2*inch))

    elements.append(P("Key Findings:", "SubSection"))
    bullets = [
        "Mobile performance needs urgent optimization (LCP > 3.8s)",
        "Several security headers missing → increased risk of attacks",
        "Missing schema markup and duplicate content issues detected",
        "Good HTTPS coverage but no HSTS → vulnerable to downgrade attacks",
    ]
    for b in bullets:
        elements.append(P(f"• {b}", "Bullet"))
    elements.append(PageBreak())

    # 3. Website Overview
    elements.append(P("3. Website Overview", "Section"))
    ov_rows = [
        ["Domain", data["domain"]],
        ["Hosting Provider", data["hosting"]],
        ["Server IP", data["ip"]],
        ["CMS / Platform", data["cms"]],
        ["SSL Status", data["ssl_valid"]],
        ["Domain Expiry", data["domain_expiry"]],
        ["Mobile Friendly", data["mobile_friendly"]],
    ]
    elements.append(Table(ov_rows, colWidths=[2.8*inch, 4*inch]))
    elements.append(PageBreak())

    # 4. Performance Analysis
    elements.append(P("4. Performance Analysis", "Section"))
    p = data["perf"]
    perf_rows = [
        ["Page Load Time", f"{p['load_time_s']} s"],
        ["First Contentful Paint", f"{p['fcp']} s"],
        ["Largest Contentful Paint", f"{p['lcp']} s"],
        ["Total Page Size", f"{p['page_size_mb']} MB"],
        ["Number of Requests", str(p["requests"])],
        ["Desktop Performance Score", f"{p['desktop_score']}/100"],
        ["Mobile Performance Score", f"{p['mobile_score']}/100"],
    ]
    elements.append(Table(perf_rows, colWidths=[3.5*inch, 3.3*inch]))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(P("Recommendation: Compress images, defer non-critical JS, use modern image formats (AVIF/WebP)", "Normal"))
    elements.append(PageBreak())

    # 5–10. Other audit sections (similar pattern – abbreviated here)
    elements.append(P("5. SEO Audit", "Section"))
    # ... add similar tables for SEO, Security, Accessibility, Technical, Content, Compliance

    # 11. Issue Classification Table
    elements.append(P("11. Issue Classification", "Section"))
    issue_data = [["Severity", "Type", "Page", "Recommendation"]]
    for i in data["issues"][:12]:  # limit to avoid huge table
        sev = i["severity"]
        issue_data.append([
            f"{emoji_severity(sev)} {sev}",
            i["type"],
            i["page"],
            i["recommend"][:60] + "..." if len(i["recommend"]) > 60 else i["recommend"]
        ])
    issue_table = Table(issue_data, colWidths=[1.4*inch, 2.4*inch, 1.6*inch, 2.4*inch])
    issue_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
        ('GRID', (0,0), (-1,-1), 0.4, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(issue_table)
    elements.append(PageBreak())

    # 12. KPI Dashboard
    elements.append(P("12. KPI & Scoring Dashboard", "Section"))
    elements.append(P(
        "Overall Score = (Perf 30%) + (SEO 25%) + (Security 25%) + (A11y 10%) + (Compliance 10%)",
        "Normal"
    ))
    # You can add radar chart / bar chart here with matplotlib → save to BytesIO → Image()

    # 13. Recommendations
    elements.append(P("13. Recommendations & Action Plan", "Section"))
    for period, items in [
        ("Immediate (0–7 days)", data["recommendations"]["immediate"]),
        ("Short Term (30 days)", data["recommendations"]["short"]),
        ("Long Term (90+ days)", data["recommendations"]["long"]),
    ]:
        elements.append(P(period, "SubSection"))
        for item in items:
            elements.append(P(f"• {item}", "Bullet"))

    elements.append(PageBreak())

    # 14. Conclusion
    elements.append(P("14. Conclusion", "Section"))
    elements.append(P(data["conclusion"], "Normal"))

    # 15. Appendix (placeholder)
    elements.append(PageBreak())
    elements.append(P("15. Appendix", "Section"))
    elements.append(P("• Raw crawl log excerpt", "Normal"))
    elements.append(P("• HTTP response headers sample", "Normal"))
    elements.append(P("• Screenshots would be embedded here", "Normal"))

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
    url = "https://example.com"
    pdf_content = generate_website_audit_pdf(url, "website-audit-report.pdf")
    print("PDF generated → website-audit-report.pdf")
