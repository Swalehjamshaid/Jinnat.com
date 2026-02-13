# -*- coding: utf-8 -*-
"""
Comprehensive single-file website audit PDF report generator
Last major fixes: Feb 2025 style duplication + url handling
Upgrades: Feb 2026 full 15-section professional report, KPI weights, safer HTML escaping,
         robust styles lookup, optional logo, colored severity, and richer data model.
"""

import io
import os
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
    PageBreak,
    Image,
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
LIGHT_ROW = colors.HexColor("#f5f7ff")

# Default KPI Weights
KPI_WEIGHTS = {
    "performance": 0.30,
    "seo":         0.25,
    "security":    0.25,
    "accessibility": 0.10,
    "compliance":    0.10,
}

# Global styles (initialized by prepare_styles())
_STYLES = None

# ────────────────────────────────────────────────
# SAFE TEXT & HELPERS
# ────────────────────────────────────────────────

def safe_text(value: Any) -> str:
    """Minimal HTML escaping for ReportLab Paragraph content.
    Do NOT escape when you intend to pass valid markup; use P(..., html=True).
    """
    if value is None:
        return ""
    s = str(value)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s

def S(style: Union[str, ParagraphStyle]) -> ParagraphStyle:
    """Return a ParagraphStyle from name or pass-through if already a style."""
    global _STYLES
    if isinstance(style, ParagraphStyle):
        return style
    if _STYLES is None:
        _STYLES = prepare_styles()
    return _STYLES[str(style)]


def P(text: str, style: Union[str, ParagraphStyle] = "Normal", bullet: Optional[str] = None, html: bool = False) -> Paragraph:
    """Create a Paragraph with either escaped text (default) or raw HTML if html=True."""
    return Paragraph(text if html else safe_text(text), S(style), bulletText=bullet)


def color_hex(c: colors.Color) -> str:
    # reportlab colors.Color.hexval() returns 'RRGGBB' without '#'
    val = c.hexval()
    return f"#{val}" if not val.startswith('#') else val


def sev_color(sev: str) -> colors.Color:
    s = (sev or '').strip().lower()
    if s == 'critical':
        return CRIT
    if s == 'high':
        return WARN
    if s == 'medium':
        return colors.HexColor('#f59e0b')  # amber-ish
    return OK


def score_color(score: Optional[float]) -> colors.Color:
    if score is None:
        return GRAY
    try:
        v = float(score)
    except Exception:
        return GRAY
    if v >= 85:
        return OK
    if v >= 65:
        return WARN
    return CRIT


def kv_table(rows: List[List[Any]], col_widths: Optional[List[float]] = None) -> Table:
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.4, colors.black),
        ('BACKGROUND', (0,0), (-1,0), LIGHT_ROW),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    return t


# ────────────────────────────────────────────────
# STYLES – safe version (never redefines built-in names)
# ────────────────────────────────────────────────

def prepare_styles():
    global _STYLES
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
        spaceBefore=2,
        spaceAfter=2
    ))

    styles.add(ParagraphStyle(
        name='Small',
        parent=styles['Normal'],
        fontSize=9,
        textColor=GRAY,
    ))

    _STYLES = styles
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

    # Sample defaults; your real collector should fill these out
    return {
        "url": url,
        "domain": domain,
        "audit_date": dt.date.today().strftime("%Y-%m-%d"),
        "generated_by": "FFTECH AI Website Auditor",
        "version": VERSION,
        # KPI section scores (0-100)
        "kpi": {
            "performance": 72,
            "seo": 68,
            "security": 75,
            "accessibility": 64,
            "compliance": 70,
        },
        "overall_score": 73,  # can be recalculated from KPI if needed
        "risk": "Medium",
        "compliance_status": "Partially Compliant",
        "total_issues": 38,
        "critical": 6,
        "summary": {
            "key_findings": [
                "LCP exceeds 3.5s on mobile home page",
                "Missing HSTS and insecure X-Frame-Options",
                "ALT text missing on 18% of images",
            ]
        },
        "overview": {
            "hosting": "Cloudflare + Vercel",
            "ip": "N/A",
            "cms": "Next.js",
            "ssl": "Valid (Let's Encrypt)",
            "domain_expiry": "N/A",
            "mobile_friendly": "Yes",
        },
        "performance": {
            "load_time": "3.9s",
            "fcp": "2.1s",
            "lcp": "3.8s",
            "page_size": "2.8 MB",
            "requests": 78,
            "desktop": 81,
            "mobile": 62,
            "recommendations": [
                "Enable HTTP/2 server push or 103 Early Hints",
                "Compress and resize hero image",
                "Defer non-critical JS and inline critical CSS",
            ]
        },
        "seo": {
            "meta_title": "Yes",
            "meta_description": "Yes",
            "h1_count": 1,
            "sitemap": "Available",
            "robots": "Found",
            "broken_links": 5,
            "missing_alt": 27,
            "canonical": "Present",
            "schema": "Partial",
        },
        "security": {
            "https": "Enforced",
            "ssl_valid": "Valid",
            "mixed_content": "None",
            "headers": "CSP: Partial; HSTS: Missing; X-Frame-Options: SAMEORIGIN",
            "vulnerabilities": "Basic scan clean",
            "admin_pages": "/admin exposed behind login",
            "open_ports": "N/A",
        },
        "accessibility": {
            "alt": "82% compliant",
            "contrast": "Minor issues on buttons",
            "aria": "Partial",
            "keyboard": "Supported",
            "score": 64,
        },
        "technical": {
            "broken_internal": 7,
            "redirects": 2,
            "errors_404": 4,
            "url_structure": "Good; uses hyphens, lowercase",
            "mobile": "Responsive",
            "structured_data": "Valid with warnings",
        },
        "content": {
            "thin": 6,
            "duplicate": 3,
            "word_count": "Median 380 words/page",
            "readability": "Grade 8",
            "keywords": "Primary keywords present on top pages",
        },
        "legal": {
            "privacy_policy": "Present",
            "terms": "Present",
            "cookies": "Banner present; preferences limited",
            "gdpr": "Partially ready",
            "contact_info": "Visible in footer",
        },
        "issues": [
            {"type": "Core Web Vitals", "severity": "Critical", "url": "/", "recommendation": "Optimize LCP image, reduce JS", "status": "Open"},
            {"type": "Security Header",  "severity": "High",     "url": "site-wide", "recommendation": "Enable HSTS", "status": "Open"},
            {"type": "Accessibility",    "severity": "Medium",   "url": "/product/*", "recommendation": "Add ALT text to images", "status": "In Progress"},
        ],
        "recommendations": {
            "immediate": ["Fix LCP", "Add HSTS"],
            "short_term": ["Optimize images", "Add schema"],
            "long_term": ["Modernize stack", "Improve content"],
        },
        "conclusion": (
            "The website demonstrates moderate technical stability; however, improvements are required in "
            "performance optimization, structured SEO implementation, and security header configuration. "
            "Immediate attention to critical findings is recommended to enhance compliance, user experience, "
            "and search engine visibility."
        ),
        "appendix": {
            "HTTP Response Headers": "server: cloudflare; content-type: text/html; ...",
            "Crawl Summary": "342 pages discovered; 298 crawled; 44 blocked by robots",
        },
        # Optional branding
        "logo_path": None,
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
# MAIN PDF GENERATOR (15 sections)
# ────────────────────────────────────────────────

def generate_audit_pdf(url_input: Union[str, dict], output_path: Optional[str] = None) -> bytes:
    data = get_audit_data(url_input)
    styles = prepare_styles()

    # Derive KPI overall score per requested formula if KPI present
    kpi = (data.get('kpi') or {}).copy()
    if kpi:
        weights = {**KPI_WEIGHTS, **(data.get('kpi_weights') or {})}
        overall = 0.0
        total_w = 0.0
        for k, w in weights.items():
            v = kpi.get(k)
            if v is not None:
                overall += float(v) * float(w)
                total_w += float(w)
        if total_w:
            kpi_overall = round(overall / total_w, 2)
            data['overall_score'] = data.get('overall_score', kpi_overall) or kpi_overall
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=50, rightMargin=50,
        topMargin=70, bottomMargin=50
    )

    elements: List[Any] = []

    # 1) COVER PAGE
    title = data.get('report_title') or 'Website Performance & Compliance Audit Report'
    elements.append(P(f"{COMPANY}", 'Small'))
    elements.append(P(title, 'TitleBig'))
    # Optional logo
    logo_path = data.get('logo_path')
    if logo_path and os.path.exists(logo_path):
        try:
            elements.append(Image(logo_path, width=180, height=60))
            elements.append(Spacer(1, 0.15*inch))
        except Exception:
            pass
    elements.append(P(f"Website URL: {data.get('url', 'N/A')}", 'Normal'))
    elements.append(P(f"Audit Date: {data.get('audit_date', 'N/A')}", 'Normal'))
    elements.append(P(f"Report Generated By: {data.get('generated_by', COMPANY)}", 'Normal'))
    elements.append(P(f"Version: {data.get('version', VERSION)}", 'Normal'))
    elements.append(PageBreak())

    # 2) EXECUTIVE SUMMARY
    elements.append(P("Executive Summary", 'Heading1'))
    score = data.get('overall_score')
    score_col = score_color(score)

    exec_rows: List[List[Any]] = [[P('Metric', 'Small'), P('Value', 'Small'), P('Notes', 'Small')]]
    exec_rows.append([
        P('Overall Website Health Score', 'Normal'),
        P(f"{score if score is not None else 'N/A'}%", 'Normal'),
        P(f"Overall: {int(score) if score is not None else 'N/A'}/100", 'Normal') if score is not None else P('', 'Normal')
    ])
    exec_rows.append([P('Risk Level', 'Normal'), P(data.get('risk', 'N/A'), 'Normal'), P('', 'Normal')])
    exec_rows.append([P('Total Issues Found', 'Normal'), P(data.get('total_issues', '0'), 'Normal'), P('', 'Normal')])
    exec_rows.append([P('Critical Issues Count', 'Normal'), P(data.get('critical', '0'), 'Normal'), P('', 'Normal')])
    exec_rows.append([P('Compliance Status', 'Normal'), P(data.get('compliance_status', 'N/A'), 'Normal'), P('', 'Normal')])

    t_exec = kv_table(exec_rows, col_widths=[2.8*inch, 1.6*inch, 2.4*inch])
    elements.append(t_exec)

    # Key findings bullets
    key_findings = (data.get('summary') or {}).get('key_findings') or []
    if key_findings:
        elements.append(Spacer(1, 0.12*inch))
        elements.append(P("Summary of Key Findings", 'Heading2'))
        for k in key_findings[:5]:
            elements.append(P(f"• {k}", 'Bullet'))
    elements.append(PageBreak())

    # 3) WEBSITE OVERVIEW
    elements.append(P("Website Overview", 'Section'))
    ov = data.get('overview') or {}
    overview_rows = [[P('Field', 'Small'), P('Value', 'Small')]]
    overview_rows += [
        [P('Domain Name', 'Normal'), P(data.get('domain', 'N/A'), 'Normal')],
        [P('Hosting Provider', 'Normal'), P(ov.get('hosting', 'N/A'), 'Normal')],
        [P('Server IP', 'Normal'), P(ov.get('ip', 'N/A'), 'Normal')],
        [P('CMS Used', 'Normal'), P(ov.get('cms', 'N/A'), 'Normal')],
        [P('SSL Certificate Status', 'Normal'), P(ov.get('ssl', 'N/A'), 'Normal')],
        [P('Domain Expiry', 'Normal'), P(ov.get('domain_expiry', 'N/A'), 'Normal')],
        [P('Mobile Friendly Status', 'Normal'), P(ov.get('mobile_friendly', 'N/A'), 'Normal')],
    ]
    elements.append(kv_table(overview_rows, col_widths=[2.8*inch, 4.0*inch]))
    elements.append(PageBreak())

    # 4) PERFORMANCE ANALYSIS
    elements.append(P("Performance Analysis", 'Section'))
    perf = data.get('performance') or {}
    perf_rows = [[P('Metric', 'Small'), P('Value', 'Small')]]
    perf_rows += [
        [P('Page Load Time', 'Normal'), P(perf.get('load_time', 'N/A'), 'Normal')],
        [P('First Contentful Paint (FCP)', 'Normal'), P(perf.get('fcp', 'N/A'), 'Normal')],
        [P('Largest Contentful Paint (LCP)', 'Normal'), P(perf.get('lcp', 'N/A'), 'Normal')],
        [P('Total Page Size', 'Normal'), P(perf.get('page_size', 'N/A'), 'Normal')],
        [P('Number of Requests', 'Normal'), P(perf.get('requests', 'N/A'), 'Normal')],
        [P('Performance Score (Desktop)', 'Normal'), P(perf.get('desktop', 'N/A'), 'Normal')],
        [P('Performance Score (Mobile)', 'Normal'), P(perf.get('mobile', 'N/A'), 'Normal')],
    ]
    elements.append(kv_table(perf_rows, col_widths=[3.2*inch, 3.6*inch]))

    recs = perf.get('recommendations') or []
    if recs:
        elements.append(Spacer(1, 0.1*inch))
        elements.append(P("Speed Optimization Recommendations", 'Heading2'))
        for r in recs:
            elements.append(P(f"• {r}", 'Bullet'))
    elements.append(PageBreak())

    # 5) SEO AUDIT
    elements.append(P("SEO Audit", 'Section'))
    seo = data.get('seo') or {}
    seo_rows = [[P('Check', 'Small'), P('Status / Value', 'Small')]]
    seo_rows += [
        [P('Meta Title Present', 'Normal'), P(seo.get('meta_title', 'N/A'), 'Normal')],
        [P('Meta Description Present', 'Normal'), P(seo.get('meta_description', 'N/A'), 'Normal')],
        [P('Heading Structure (H1 Count)', 'Normal'), P(seo.get('h1_count', 'N/A'), 'Normal')],
        [P('Sitemap.xml Availability', 'Normal'), P(seo.get('sitemap', 'N/A'), 'Normal')],
        [P('Robots.txt Status', 'Normal'), P(seo.get('robots', 'N/A'), 'Normal')],
        [P('Broken Links', 'Normal'), P(seo.get('broken_links', 'N/A'), 'Normal')],
        [P('Image ALT Tags Missing', 'Normal'), P(seo.get('missing_alt', 'N/A'), 'Normal')],
        [P('Canonical Tags', 'Normal'), P(seo.get('canonical', 'N/A'), 'Normal')],
        [P('Schema Markup', 'Normal'), P(seo.get('schema', 'N/A'), 'Normal')],
    ]
    elements.append(kv_table(seo_rows, col_widths=[3.2*inch, 3.6*inch]))
    elements.append(PageBreak())

    # 6) SECURITY AUDIT
    elements.append(P("Security Audit", 'Section'))
    sec = data.get('security') or {}
    sec_rows = [[P('Check', 'Small'), P('Status / Value', 'Small')]]
    sec_rows += [
        [P('HTTPS Enforced', 'Normal'), P(sec.get('https', 'N/A'), 'Normal')],
        [P('SSL Validity', 'Normal'), P(sec.get('ssl_valid', 'N/A'), 'Normal')],
        [P('Mixed Content Issues', 'Normal'), P(sec.get('mixed_content', 'N/A'), 'Normal')],
        [P('Security Headers', 'Normal'), P(sec.get('headers', 'N/A'), 'Normal')],
        [P('Vulnerability Scan (Basic)', 'Normal'), P(sec.get('vulnerabilities', 'N/A'), 'Normal')],
        [P('Exposed Admin Pages', 'Normal'), P(sec.get('admin_pages', 'N/A'), 'Normal')],
        [P('Open Ports', 'Normal'), P(sec.get('open_ports', 'N/A'), 'Normal')],
    ]
    elements.append(kv_table(sec_rows, col_widths=[3.2*inch, 3.6*inch]))
    elements.append(PageBreak())

    # 7) ACCESSIBILITY (WCAG Compliance)
    elements.append(P("Accessibility (WCAG Compliance)", 'Section'))
    acc = data.get('accessibility') or {}
    acc_rows = [[P('Check', 'Small'), P('Status / Value', 'Small')]]
    acc_rows += [
        [P('Image ALT Compliance', 'Normal'), P(acc.get('alt', 'N/A'), 'Normal')],
        [P('Contrast Issues', 'Normal'), P(acc.get('contrast', 'N/A'), 'Normal')],
        [P('ARIA Labels', 'Normal'), P(acc.get('aria', 'N/A'), 'Normal')],
        [P('Keyboard Navigation Support', 'Normal'), P(acc.get('keyboard', 'N/A'), 'Normal')],
        [P('Accessibility Score', 'Normal'), P(acc.get('score', 'N/A'), 'Normal')],
    ]
    elements.append(kv_table(acc_rows, col_widths=[3.2*inch, 3.6*inch]))
    elements.append(PageBreak())

    # 8) TECHNICAL STRUCTURE
    elements.append(P("Technical Structure", 'Section'))
    tech = data.get('technical') or {}
    tech_rows = [[P('Check', 'Small'), P('Status / Value', 'Small')]]
    tech_rows += [
        [P('Broken Internal Links', 'Normal'), P(tech.get('broken_internal', 'N/A'), 'Normal')],
        [P('Redirect Chains', 'Normal'), P(tech.get('redirects', 'N/A'), 'Normal')],
        [P('404 Errors', 'Normal'), P(tech.get('errors_404', 'N/A'), 'Normal')],
        [P('URL Structure Quality', 'Normal'), P(tech.get('url_structure', 'N/A'), 'Normal')],
        [P('Mobile Responsiveness', 'Normal'), P(tech.get('mobile', 'N/A'), 'Normal')],
        [P('Structured Data Validation', 'Normal'), P(tech.get('structured_data', 'N/A'), 'Normal')],
    ]
    elements.append(kv_table(tech_rows, col_widths=[3.2*inch, 3.6*inch]))
    elements.append(PageBreak())

    # 9) CONTENT QUALITY REVIEW
    elements.append(P("Content Quality Review", 'Section'))
    cont = data.get('content') or {}
    cont_rows = [[P('Check', 'Small'), P('Status / Value', 'Small')]]
    cont_rows += [
        [P('Thin Content Pages', 'Normal'), P(cont.get('thin', 'N/A'), 'Normal')],
        [P('Duplicate Content', 'Normal'), P(cont.get('duplicate', 'N/A'), 'Normal')],
        [P('Word Count Analysis', 'Normal'), P(cont.get('word_count', 'N/A'), 'Normal')],
        [P('Readability Score', 'Normal'), P(cont.get('readability', 'N/A'), 'Normal')],
        [P('Keyword Usage', 'Normal'), P(cont.get('keywords', 'N/A'), 'Normal')],
    ]
    elements.append(kv_table(cont_rows, col_widths=[3.2*inch, 3.6*inch]))
    elements.append(PageBreak())

    # 10) COMPLIANCE & LEGAL
    elements.append(P("Compliance & Legal", 'Section'))
    legal = data.get('legal') or {}
    legal_rows = [[P('Check', 'Small'), P('Status / Value', 'Small')]]
    legal_rows += [
        [P('Privacy Policy Page', 'Normal'), P(legal.get('privacy_policy', 'N/A'), 'Normal')],
        [P('Terms & Conditions', 'Normal'), P(legal.get('terms', 'N/A'), 'Normal')],
        [P('Cookie Consent', 'Normal'), P(legal.get('cookies', 'N/A'), 'Normal')],
        [P('GDPR Readiness', 'Normal'), P(legal.get('gdpr', 'N/A'), 'Normal')],
        [P('Contact Information Visible', 'Normal'), P(legal.get('contact_info', 'N/A'), 'Normal')],
    ]
    elements.append(kv_table(legal_rows, col_widths=[3.2*inch, 3.6*inch]))
    elements.append(PageBreak())

    # 11) ISSUE CLASSIFICATION TABLE
    elements.append(P("Issue Classification Table", 'Section'))

    issues: List[Dict[str, Any]] = data.get('issues') or []
    issue_table_rows: List[List[Any]] = [
        [P('Issue Type', 'Small'), P('Severity', 'Small'), P('Page URL', 'Small'), P('Recommendation', 'Small'), P('Status', 'Small')]
    ]

    for it in issues:
        sev = it.get('severity') or it.get('sev') or 'Medium'
        col = color_hex(sev_color(sev))
        sev_label = P(f"<b><font color='{col}'>{safe_text(sev.title())}</font></b>", 'Normal', html=True)
        issue_table_rows.append([
            P(it.get('type') or it.get('desc') or '-', 'Normal'),
            sev_label,
            P(it.get('url', '-') , 'Normal'),
            P(it.get('recommendation', '-') , 'Normal'),
            P(it.get('status', 'Open'), 'Normal'),
        ])

    it_table = Table(issue_table_rows, colWidths=[1.6*inch, 0.9*inch, 1.7*inch, 2.0*inch, 0.8*inch])
    it_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.4, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(it_table)
    elements.append(Spacer(1, 0.08*inch))

    # Severity legend
    legend_rows = [
        [P('Severity Levels', 'Small'), P('Meaning', 'Small')],
        [P('Critical', 'Normal'), P('Immediate action required', 'Small')],
        [P('High', 'Normal'), P('Prioritize within sprint', 'Small')],
        [P('Medium', 'Normal'), P('Fix as part of routine improvements', 'Small')],
        [P('Low', 'Normal'), P('Minor enhancement / housekeeping', 'Small')],
    ]
    elements.append(kv_table(legend_rows, col_widths=[1.3*inch, 5.5*inch]))
    elements.append(PageBreak())

    # 12) KPI & SCORING DASHBOARD
    elements.append(P("KPI & Scoring Dashboard", 'Section'))
    kpi = data.get('kpi') or {}
    weights = {**KPI_WEIGHTS, **(data.get('kpi_weights') or {})}

    kpi_rows: List[List[Any]] = [[P('KPI', 'Small'), P('Score (%)', 'Small'), P('Weight', 'Small'), P('Weighted', 'Small')]]
    overall_calc = 0.0
    total_w = 0.0

    for name in ['performance','seo','security','accessibility','compliance']:
        v = kpi.get(name)
        w = float(weights.get(name, 0.0))
        weighted = round((float(v)*w), 2) if v is not None else 0.0
        overall_calc += weighted
        total_w += w if v is not None else 0.0
        kpi_rows.append([
            P(name.capitalize(), 'Normal'),
            P('-' if v is None else f"{v}", 'Normal'),
            P(f"{int(w*100)}%", 'Normal'),
            P('-' if v is None else f"{weighted}", 'Normal'),
        ])

    overall_final = round(overall_calc / total_w, 2) if total_w else data.get('overall_score', 'N/A')
    kpi_rows.append([P('Overall Website Health Score', 'Normal'), P(f"{overall_final}", 'Normal'), P('—', 'Normal'), P('—', 'Normal')])

    elements.append(kv_table(kpi_rows, col_widths=[2.4*inch, 1.4*inch, 1.4*inch, 1.6*inch]))

    # Formula note
    formula_lines = [
        "Overall Score = (Performance 30%) + (SEO 25%) + (Security 25%) + (Accessibility 10%) + (Compliance 10%)"
    ]
    elements.append(Spacer(1, 0.08*inch))
    for line in formula_lines:
        elements.append(P(line, 'Small'))
    elements.append(PageBreak())

    # 13) RECOMMENDATIONS & ACTION PLAN
    elements.append(P("Recommendations & Action Plan", 'Section'))
    recs = data.get('recommendations') or {}

    for title, key in [("Immediate (0–7 Days)", 'immediate'), ("Short Term (30 Days)", 'short_term'), ("Long Term (90 Days)", 'long_term')]:
        items = recs.get(key) or []
        elements.append(P(title, 'Heading2'))
        if items:
            for item in items:
                elements.append(P(f"• {item}", 'Bullet'))
        else:
            elements.append(P("No items provided.", 'Small'))
        elements.append(Spacer(1, 0.06*inch))
    elements.append(PageBreak())

    # 14) CONCLUSION
    elements.append(P("Conclusion", 'Section'))
    elements.append(P(data.get('conclusion', ''), 'Normal'))
    elements.append(PageBreak())

    # 15) APPENDIX
    elements.append(P("Appendix", 'Section'))
    appendix = data.get('appendix') or {}
    if appendix:
        for key, value in appendix.items():
            elements.append(P(key, 'Heading2'))
            elements.append(P(str(value), 'Normal'))
            elements.append(Spacer(1, 0.08*inch))
    else:
        elements.append(P("No appendix data provided.", 'Small'))

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
    generate_audit_pdf(test_url, os.path.join(os.path.dirname(__file__), "audit-report.pdf"))
    print("PDF written to audit-report.pdf")
