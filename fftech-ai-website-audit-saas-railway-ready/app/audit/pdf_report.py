# -*- coding: utf-8 -*-
"""
app/audit/pdf_report.py

Enterprise PDF generator (ReportLab) for WebsiteAuditRunner results.
- Consumes dict produced by runner_result_to_audit_data(...) in app/audit/runner.py
- Returns raw PDF bytes (for runner to write to disk)
- No network calls; safe for Railway
- Charts rendered via matplotlib (Agg)

Sections covered:
  1) Cover Page (logo, URL, date/time, report ID hash, generated-by SaaS, confidentiality)
  2) Executive Summary (CEO): overall score, category scores, risk level, radar+bar charts,
     top critical issues (derived), estimated business impact
  3) Website Overview (domain/ip/cms heuristic/N/A safe, SSL/HSTS/redirect status if present, load time, page size, total requests)
  4) SEO Audit (on-page + technical; N/A where runner doesn’t provide fields)
  5) Performance Audit (FCP/LCP/TTI/TBT placeholders; compression/caching if present else N/A)
  6) Security Audit (SSL/HSTS headers status from runner; headers/CSP/etc -> N/A if absent)
  7) Accessibility Audit (ALT stats available; others N/A; estimated WCAG level heuristic)
  8) UX Audit (N/A placeholders)
  9) Broken Link Analysis (N/A placeholders; runner does not crawl links)
 10) Analytics & Tracking (N/A placeholders)
 11) Critical Issues Summary Table (color-coded)
 12) Recommendations & Fix Roadmap (Immediate / Short-Term / Long-Term)
 13) Scoring Methodology (weights/formula summary)
 14) Appendix (technical: headers/DOM/resources—limited by runner data)
 15) Conclusion (professional statement)

Note: Many advanced measurements need lab tools/APIs (Lighthouse, PSI, CWV, GeoIP, Wappalyzer, etc.)
They are marked as N/A when not present in the runner result.
"""

from __future__ import annotations
import io
import os
import re
import json
import time
import math
import socket
import hashlib
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# ReportLab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
)

# Charts
import matplotlib
matplotlib.use("Agg")  # Railway/headless safe
import matplotlib.pyplot as plt
import numpy as np

# ------------------------------------------------------------
# BRANDING / COLORS / ENV
# ------------------------------------------------------------
PDF_BRAND_NAME = os.getenv("PDF_BRAND_NAME", "FF Tech")
PDF_LOGO_PATH = os.getenv("PDF_LOGO_PATH", "")  # optional
SAAS_NAME = os.getenv("PDF_REPORT_TITLE", "Website Audit Report")
PRIMARY_DARK = colors.HexColor("#1A2B3C")
ACCENT_BLUE = colors.HexColor("#3498DB")
SUCCESS_GREEN = colors.HexColor("#27AE60")
CRITICAL_RED = colors.HexColor("#C0392B")
WARNING_ORANGE = colors.HexColor("#F39C12")
MUTED_GREY = colors.HexColor("#7F8C8D")
PURPLE = colors.HexColor("#8E44AD")

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def _now_str() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")

def _hostname(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""

def _get_ip(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except Exception:
        return "Unknown"

def _kb(n: int) -> str:
    try:
        return f"{round(int(n)/1024.0, 1)} KB"
    except Exception:
        return "N/A"

def _risk_from_score(overall: int) -> str:
    try:
        o = int(overall)
    except Exception:
        o = 0
    if o >= 85: return "Low"
    if o >= 70: return "Medium"
    if o >= 50: return "High"
    return "Critical"

def _safe_get(d: dict, path: List[str], default: Any = "N/A") -> Any:
    cur = d
    try:
        for k in path:
            cur = cur.get(k, {})
        if cur == {}:
            return default
        return cur
    except Exception:
        return default

def _int_or(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default

def _bool_to_yesno(v: Any) -> str:
    return "Yes" if bool(v) else "No"

def _hash_integrity(audit_data: dict) -> str:
    # Stable JSON dump for digest
    raw = json.dumps(audit_data, sort_keys=True, ensure_ascii=False).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest().upper()

def _short_id_from_hash(h: str) -> str:
    return h[:12]

def _score_or_na(scores: dict, key: str) -> Optional[int]:
    v = scores.get(key)
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None

def _color_for_priority(priority: str):
    p = priority.lower()
    if "🔴" in priority or p == "critical":
        return CRITICAL_RED
    if "🟠" in priority or p == "high":
        return WARNING_ORANGE
    if "🟡" in priority or p == "medium":
        return colors.Color(0.98, 0.91, 0.4)  # yellow-ish
    return SUCCESS_GREEN  # low

# ------------------------------------------------------------
# ISSUE DERIVATION (from runner breakdown) — no network calls
# ------------------------------------------------------------
def derive_critical_issues(audit: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Produce a small list of issues with priority, category, impact, and fix
    based on runner-provided breakdown values. Only uses available data.
    """
    issues: List[Dict[str, str]] = []
    br = audit.get("breakdown", {})

    # Security issues
    sec = br.get("security", {})
    if sec:
        if not sec.get("https", True):
            issues.append({
                "priority": "🔴 Critical",
                "issue": "Site is served over HTTP (no TLS).",
                "category": "Security",
                "impact": "High data interception risk; user trust loss.",
                "fix": "Install TLS certificate and force HTTPS site-wide (HSTS)."
            })
        if sec.get("status_code", 200) >= 400:
            issues.append({
                "priority": "🟠 High",
                "issue": f"Non-OK status code ({sec.get('status_code')}).",
                "category": "Security",
                "impact": "Service reliability issues; broken experience.",
                "fix": "Ensure origin responds 200 for main document; fix server/app errors."
            })
        if sec.get("https", False) and not sec.get("hsts", False):
            issues.append({
                "priority": "🟡 Medium",
                "issue": "HSTS header not detected.",
                "category": "Security",
                "impact": "HTTPS downgrade risk on some clients.",
                "fix": "Enable Strict-Transport-Security with preload where appropriate."
            })

    # Performance issues
    perf = br.get("performance", {})
    pex = perf.get("extras", {})
    load_ms = _int_or(pex.get("load_ms", 0), 0)
    size_b = _int_or(pex.get("bytes", 0), 0)
    if load_ms > 3000:
        issues.append({
            "priority": "🟠 High" if load_ms > 5000 else "🟡 Medium",
            "issue": f"High load time ({load_ms} ms).",
            "category": "Performance",
            "impact": "Conversion loss; poor UX & Core Web Vitals risk.",
            "fix": "Optimize server TTFB, compress assets, lazy load below-the-fold media, defer non-critical JS."
        })
    if size_b > 1_500_000:
        issues.append({
            "priority": "🟡 Medium",
            "issue": f"Large page size ({_kb(size_b)}).",
            "category": "Performance",
            "impact": "Slower loads on mobile/slow networks; bounce risk.",
            "fix": "Compress images (WebP/AVIF), minify & split JS/CSS, remove unused libraries."
        })

    # SEO issues
    seo = br.get("seo", {})
    sex = seo.get("extras", {})
    if not sex.get("title"):
        issues.append({
            "priority": "🔴 Critical",
            "issue": "Missing <title> tag.",
            "category": "SEO",
            "impact": "Poor indexing & SERP CTR.",
            "fix": "Add keyword-optimized title (~55–60 chars) per page."
        })
    if sex.get("h1_count", 0) == 0:
        issues.append({
            "priority": "🟠 High",
            "issue": "Missing H1 heading.",
            "category": "SEO",
            "impact": "Weak topical clarity & accessibility.",
            "fix": "Add a single, descriptive H1 targeting the primary keyword."
        })
    if not seo:
        pass

    # Accessibility issues
    imgs_missing = _int_or(sex.get("images_missing_alt", 0), 0)
    imgs_total = _int_or(sex.get("images_total", 0), 0)
    if imgs_missing > 0:
        issues.append({
            "priority": "🟡 Medium" if imgs_missing < 10 else "🟠 High",
            "issue": f"Images missing ALT text ({imgs_missing}/{imgs_total}).",
            "category": "Accessibility",
            "impact": "Screen readers can’t interpret visuals; compliance risk.",
            "fix": "Add descriptive alt text to all meaningful images."
        })

    # Sort by priority order: Critical, High, Medium, Low
    priority_weight = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Medium": 2, "🟢 Low": 3}
    issues.sort(key=lambda x: priority_weight.get(x["priority"], 9))
    return issues[:12]  # cap

# ------------------------------------------------------------
# CHARTS
# ------------------------------------------------------------
def _radar_chart(scores: Dict[str, Any]) -> io.BytesIO:
    # Accepts any set of categories; limit to 5–6 for readability
    order = ["seo", "performance", "security", "accessibility", "ux", "links"]
    labels = []
    values = []
    for k in order:
        if k in scores:
            labels.append(k.upper())
            try:
                values.append(int(scores[k]))
            except Exception:
                values.append(0)
    if not labels:
        labels = ["SCORE"]
        values = [0]

    # prepare
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(4.8, 4.8), subplot_kw=dict(polar=True))
    ax.fill(angles, values, color='#3498DB', alpha=0.25)
    ax.plot(angles, values, color='#2980B9', linewidth=2)
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9, fontweight='bold')
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=140)
    plt.close(fig)
    buf.seek(0)
    return buf

def _bar_chart(scores: Dict[str, Any]) -> io.BytesIO:
    cats = [k for k in ["seo", "performance", "security", "accessibility", "ux", "links"] if k in scores]
    vals = [int(scores.get(c, 0)) for c in cats]
    if not cats:
        cats, vals = ["OVERALL"], [int(scores.get("overall", 0))]
    colors_list = ['#2E86C1', '#1ABC9C', '#C0392B', '#8E44AD', '#F39C12', '#16A085'][:len(cats)]
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    bars = ax.bar([c.upper() for c in cats], vals, color=colors_list)
    ax.set_ylim(0, 100)
    ax.set_ylabel('Score')
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, v + 1, f"{v}", ha='center', fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=140)
    plt.close(fig)
    buf.seek(0)
    return buf

# ------------------------------------------------------------
# PDF GENERATOR
# ------------------------------------------------------------
class PDFReport:
    def __init__(self, audit: Dict[str, Any]):
        self.data = audit
        self.styles = getSampleStyleSheet()
        # Custom styles
        self.styles.add(ParagraphStyle('Muted', fontSize=8, textColor=MUTED_GREY))
        self.styles.add(ParagraphStyle('H2', parent=self.styles['Heading2'], textColor=PRIMARY_DARK))
        self.styles.add(ParagraphStyle('H3', parent=self.styles['Heading3'], textColor=PRIMARY_DARK))
        self.styles.add(ParagraphStyle('KPI', fontSize=16, textColor=PRIMARY_DARK))
        self.styles.add(ParagraphStyle('Note', fontSize=9, textColor=MUTED_GREY, leading=12))
        self.styles.add(ParagraphStyle('Tiny', fontSize=7, textColor=MUTED_GREY))

        # Precompute integrity hash & report id
        self.integrity = _hash_integrity(audit)
        self.report_id = _short_id_from_hash(self.integrity)

        # Safe shorthands
        self.brand = audit.get("brand_name", PDF_BRAND_NAME) or PDF_BRAND_NAME
        self.client = audit.get("client_name", "N/A")
        self.url = audit.get("audited_url", "N/A")
        self.site_name = audit.get("website_name", self.url)
        self.audit_dt = audit.get("audit_datetime", _now_str())
        self.scores = audit.get("scores", {})
        # Append Accessibility/UX scores if provided by any upstream
        self.scores.setdefault("accessibility", audit.get("breakdown", {}).get("accessibility", {}).get("score", 0))
        self.scores.setdefault("ux", audit.get("breakdown", {}).get("ux", {}).get("score", 0))
        self.overall = _int_or(self.data.get("overall_score", self.scores.get("overall", 0)), 0)
        self.risk = _risk_from_score(self.overall)

        # Derive issues
        self.issues = derive_critical_issues(self.data)

        # Overview heuristics
        host = _hostname(self.url)
        self.overview = {
            "domain": host or "N/A",
            "ip": _get_ip(host) if host else "Unknown",
            "hosting_provider": "N/A (not detected)",
            "server_location": "N/A (GeoIP not integrated)",
            "cms": "Custom/Unknown",
            "ssl_status": "HTTPS" if _safe_get(self.data, ["breakdown", "security"]).get("https", False) else "HTTP",
            "http_to_https": "N/A",
            "load_ms": _int_or(_safe_get(self.data, ["breakdown", "performance", "extras"]).get("load_ms", 0), 0),
            "page_size": _kb(_int_or(_safe_get(self.data, ["breakdown", "performance", "extras"]).get("bytes", 0), 0)),
            "total_requests_approx": int(
                _int_or(_safe_get(self.data, ["breakdown", "performance", "extras"]).get("scripts", 0), 0) +
                _int_or(_safe_get(self.data, ["breakdown", "performance", "extras"]).get("styles", 0), 0) + 1
            )
        }

    # ------------- building blocks -------------
    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(PRIMARY_DARK)
        canvas.drawString(inch, 0.5*inch, f"{self.brand} | Integrity: {self.integrity[:16]}…")
        canvas.drawRightString(A4[0]-inch, 0.5*inch, f"Page {doc.page}")
        canvas.restoreState()

    def _section_title(self, text: str) -> Paragraph:
        return Paragraph(text, self.styles['Heading1'])

    def _kvr(self, key: str, val: str) -> List:
        return [Paragraph(f"<b>{key}</b>", self.styles['Normal']), Paragraph(val, self.styles['Normal'])]

    def _table(self, rows: List[List[Any]], colWidths: Optional[List[float]] = None, header_bg=colors.whitesmoke, fontsize=9):
        t = Table(rows, colWidths=colWidths)
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), header_bg),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTSIZE', (0,0), (-1,-1), fontsize),
        ]))
        return t

    # ------------- sections -------------
    def cover_page(self, elems: List[Any]):
        elems.append(Spacer(1, 0.6*inch))
        # Logo (optional)
        logo_path = PDF_LOGO_PATH
        if isinstance(PDF_LOGO_PATH, str) and os.path.exists(PDF_LOGO_PATH):
            try:
                elems.append(Image(PDF_LOGO_PATH, width=1.8*inch, height=1.8*inch))
                elems.append(Spacer(1, 0.2*inch))
            except Exception:
                pass

        elems.append(Paragraph(self.brand.upper(), ParagraphStyle('Brand', fontSize=28, textColor=PRIMARY_DARK, fontName='Helvetica-Bold')))
        elems.append(Paragraph("Website Performance & Compliance Dossier", self.styles['Title']))
        elems.append(Spacer(1, 0.25*inch))

        rows = [
            ["Website URL Audited", self.url],
            ["Audit Date & Time", self.audit_dt],
            ["Report ID", self.report_id],
            ["Generated By", SAAS_NAME],
        ]
        elems.append(self._table(rows, colWidths=[2.2*inch, 3.9*inch]))
        elems.append(Spacer(1, 0.2*inch))
        # Confidentiality
        notice = ("This report contains confidential and proprietary information intended solely for the recipient. "
                  "Unauthorized distribution is prohibited.")
        elems.append(Paragraph(notice, self.styles['Muted']))
        elems.append(PageBreak())

    def toc_page(self, elems: List[Any]):
        elems.append(Paragraph("Contents", self.styles['Heading1']))
        bullets = [
            "Executive Summary",
            "Website Overview",
            "SEO Audit",
            "Performance Audit",
            "Security Audit",
            "Accessibility Audit",
            "User Experience (UX) Audit",
            "Broken Link Analysis",
            "Analytics & Tracking",
            "Critical Issues Summary",
            "Recommendations & Fix Roadmap",
            "Scoring Methodology",
            "Appendix (Technical Details)",
            "Conclusion",
        ]
        for b in bullets:
            elems.append(Paragraph(f"• {b}", self.styles['Normal']))
        elems.append(Spacer(1, 0.1*inch))
        elems.append(Paragraph("Note: Page numbers are included in the footer.", self.styles['Muted']))
        elems.append(PageBreak())

    def executive_summary(self, elems: List[Any]):
        elems.append(self._section_title("Executive Health Summary"))

        # Charts
        radar = Image(_radar_chart(self.scores), width=2.9*inch, height=2.9*inch)
        bars = Image(_bar_chart(self.scores), width=3.2*inch, height=2.4*inch)
        chart_tbl = Table([[radar, bars]], colWidths=[3.0*inch, 3.3*inch])
        chart_tbl.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        elems.append(chart_tbl)
        elems.append(Spacer(1, 0.15*inch))

        # KPI grid
        krows = [
            ["Overall Website Health Score", f"{self.overall}/100"],
            ["Overall Risk Level", self.risk],
            ["SEO Score", str(_int_or(self.scores.get("seo", 0), 0))],
            ["Performance Score", str(_int_or(self.scores.get("performance", 0), 0))],
            ["Security Score", str(_int_or(self.scores.get("security", 0), 0))],
            ["Accessibility Score", str(_int_or(self.scores.get("accessibility", 0), 0))],
            ["UX Score", str(_int_or(self.scores.get("ux", 0), 0))],
        ]
        elems.append(self._table(krows, colWidths=[2.7*inch, 3.6*inch]))

        elems.append(Spacer(1, 0.12*inch))
        elems.append(Paragraph("Top Critical Issues & Estimated Business Impact", self.styles['H2']))

        if not self.issues:
            elems.append(Paragraph("No critical issues derived from available data.", self.styles['Normal']))
        else:
            rows = [["Priority", "Issue", "Category", "Impact", "Recommended Fix"]]
            for i in self.issues[:5]:  # top 5
                rows.append([i["priority"], i["issue"], i["category"], i["impact"], i["fix"]])
            t = self._table(rows, colWidths=[0.9*inch, 2.3*inch, 0.9*inch, 1.6*inch, 1.6*inch])
            # Header color
            t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), ACCENT_BLUE),
                                   ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                                   ('FONTSIZE', (0,0), (-1,-1), 8)]))
            elems.append(t)
        elems.append(PageBreak())

    def website_overview(self, elems: List[Any]):
        elems.append(self._section_title("Website Overview"))
        o = self.overview
        rows = [
            ["Domain Name", o["domain"]],
            ["IP Address", o["ip"]],
            ["Hosting Provider", o["hosting_provider"]],
            ["Server Location", o["server_location"]],
            ["CMS Detected", o["cms"]],
            ["SSL Status", o["ssl_status"]],
            ["HTTP → HTTPS redirect", o["http_to_https"]],
            ["Page Load Time", f"{o['load_ms']} ms"],
            ["Page Size", o["page_size"]],
            ["Total Requests (approx)", str(o["total_requests_approx"])],
        ]
        elems.append(self._table(rows, colWidths=[2.6*inch, 3.7*inch]))
        elems.append(PageBreak())

    def seo_section(self, elems: List[Any]):
        elems.append(self._section_title("SEO Audit"))
        seo = _safe_get(self.data, ["breakdown", "seo"], {})
        ex = seo.get("extras", {})
        title = ex.get("title") or ""
        title_len = len(title)
        meta_desc_present = ex.get("meta_description_present", False)
        canonical = ex.get("canonical") or ""
        h1_count = ex.get("h1_count", 0)
        images_total = ex.get("images_total", 0)
        images_missing = ex.get("images_missing_alt", 0)

        # On-Page
        elems.append(Paragraph("On-Page SEO", self.styles['H2']))
        on_rows = [
            ["Title tag (length + optimization)", f"{title_len} chars" if title else "Missing"],
            ["Meta description (length + optimization)", "Present" if meta_desc_present else "Missing"],
            ["H1, H2 structure", f"H1 count: {h1_count}; H2: N/A"],
            ["Keyword density", "N/A"],
            ["Canonical tag presence", "Yes" if canonical else "No"],
            ["Robots.txt status", "N/A"],
            ["Sitemap.xml status", "N/A"],
            ["Open Graph tags", "N/A"],
            ["Twitter Card tags", "N/A"],
            ["Image ALT attributes missing", f"{images_missing}/{images_total}"],
            ["Broken internal links", "N/A"],
        ]
        elems.append(self._table(on_rows, colWidths=[3.0*inch, 3.3*inch]))
        elems.append(Spacer(1, 0.12*inch))

        # Technical
        elems.append(Paragraph("Technical SEO", self.styles['H2']))
        tech_rows = [
            ["Indexability", "N/A"],
            ["Mobile responsiveness", "N/A"],
            ["Core Web Vitals (if API integrated)", "N/A"],
            ["Structured data presence (Schema.org)", "N/A"],
            ["Redirect chains", "N/A"],
            ["Duplicate content detection", "N/A"],
        ]
        elems.append(self._table(tech_rows, colWidths=[3.0*inch, 3.3*inch]))
        elems.append(PageBreak())

    def performance_section(self, elems: List[Any]):
        elems.append(self._section_title("Performance Audit"))
        pex = _safe_get(self.data, ["breakdown", "performance", "extras"], {})
        rows = [
            ["First Contentful Paint (FCP)", "N/A"],
            ["Largest Contentful Paint (LCP)", "N/A"],
            ["Time to Interactive (TTI)", "N/A"],
            ["Total Blocking Time", "N/A"],
            ["PageSpeed score (if API)", "N/A"],
            ["Compression enabled (GZIP/Brotli)", "N/A"],
            ["Caching headers", "N/A"],
            ["Minified CSS/JS?", "N/A"],
            ["Image optimization status", "N/A"],
            ["Lazy loading status", "N/A"],
            ["Measured Load Time", f"{_int_or(pex.get('load_ms', 0), 0)} ms"],
            ["Measured Page Size", _kb(_int_or(pex.get('bytes', 0), 0))],
            ["Script/CSS Count", f"{_int_or(pex.get('scripts', 0), 0)} JS / {_int_or(pex.get('styles', 0), 0)} CSS"],
        ]
        elems.append(self._table(rows, colWidths=[3.6*inch, 2.7*inch]))
        elems.append(PageBreak())

    def security_section(self, elems: List[Any]):
        elems.append(self._section_title("Security Audit"))
        sec = _safe_get(self.data, ["breakdown", "security"], {})
        rows = [
            ["SSL Certificate Validity", "N/A"],
            ["HSTS Enabled?", _bool_to_yesno(sec.get("hsts", False)) if sec else "N/A"],
            ["Content-Security-Policy", "N/A"],
            ["X-Frame-Options", "N/A"],
            ["X-XSS-Protection", "N/A"],
            ["X-Content-Type-Options", "N/A"],
            ["Mixed content issues", "N/A"],
            ["Exposed admin panels", "N/A"],
            ["HTTP methods allowed", "N/A"],
            ["Cookies secure/HttpOnly", "N/A"],
            ["Origin Status Code", str(sec.get("status_code", "N/A"))],
            ["HTTPS Enabled", _bool_to_yesno(sec.get("https", False))],
        ]
        elems.append(self._table(rows, colWidths=[3.1*inch, 3.2*inch]))
        elems.append(PageBreak())

    def accessibility_section(self, elems: List[Any]):
        elems.append(self._section_title("Accessibility Audit"))
        ex = _safe_get(self.data, ["breakdown", "seo", "extras"], {})  # only ALT stats available
        missing_alt = _int_or(ex.get("images_missing_alt", 0), 0)
        imgs_total = _int_or(ex.get("images_total", 0), 0)
        # Estimated level
        if missing_alt == 0 and imgs_total > 0:
            level = "WCAG A (est.)"
        elif missing_alt <= max(1, imgs_total // 10):
            level = "WCAG AA (est.)"
        else:
            level = "Below AA (est.)"

        rows = [
            ["Missing ALT tags", f"{missing_alt}/{imgs_total}"],
            ["Contrast ratio issues", "N/A"],
            ["Missing ARIA labels", "N/A"],
            ["Form label issues", "N/A"],
            ["Keyboard navigation support", "N/A"],
            ["Semantic HTML structure", "N/A"],
            ["Compliance Level (estimated)", level],
        ]
        elems.append(self._table(rows, colWidths=[3.1*inch, 3.2*inch]))
        elems.append(PageBreak())

    def ux_section(self, elems: List[Any]):
        elems.append(self._section_title("User Experience (UX) Audit"))
        rows = [
            ["Mobile friendliness", "N/A"],
            ["Viewport configuration", "N/A"],
            ["Navigation clarity", "N/A"],
            ["CTA visibility", "N/A"],
            ["Pop-up intrusiveness", "N/A"],
            ["Broken buttons", "N/A"],
            ["Form usability", "N/A"],
        ]
        elems.append(self._table(rows, colWidths=[3.1*inch, 3.2*inch]))
        elems.append(PageBreak())

    def broken_links_section(self, elems: List[Any]):
        elems.append(self._section_title("Broken Link Analysis"))
        rows = [
            ["URL", "Status Code", "Anchor Text", "Type"],
            ["N/A", "N/A", "N/A", "N/A"]
        ]
        elems.append(self._table(rows, colWidths=[3.0*inch, 0.9*inch, 1.5*inch, 0.9*inch], fontsize=8))
        elems.append(Paragraph("Note: Deep link crawl is not performed by the runner; integrate a crawler to populate this table.", self.styles['Note']))
        elems.append(PageBreak())

    def analytics_tracking_section(self, elems: List[Any]):
        elems.append(self._section_title("Analytics & Tracking"))
        rows = [
            ["Google Analytics (GA4)", "N/A"],
            ["Google Analytics (UA)", "N/A"],
            ["Google Tag Manager", "N/A"],
            ["Facebook Pixel", "N/A"],
            ["Conversion tracking", "N/A"],
            ["Missing tracking warnings", "If none detected in markup, add GTM/GA4."],
        ]
        elems.append(self._table(rows, colWidths=[3.1*inch, 3.2*inch]))
        elems.append(PageBreak())

    def critical_issues_section(self, elems: List[Any]):
        elems.append(self._section_title("Critical Issues Summary"))
        if not self.issues:
            elems.append(Paragraph("No critical issues derived from available data.", self.styles['Normal']))
            elems.append(PageBreak())
            return
        rows = [["Priority", "Issue", "Category", "Impact", "Recommended Fix"]]
        for i in self.issues:
            rows.append([i["priority"], i["issue"], i["category"], i["impact"], i["fix"]])
        t = self._table(rows, colWidths=[0.9*inch, 2.3*inch, 0.9*inch, 1.6*inch, 1.6*inch], header_bg=ACCENT_BLUE, fontsize=8)
        t.setStyle(TableStyle([('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke)]))
        elems.append(t)
        elems.append(PageBreak())

    def recommendations_section(self, elems: List[Any]):
        elems.append(self._section_title("Recommendations & Fix Roadmap"))

        # Immediate fixes (0–7 days)
        imm = [
            "Force HTTPS & enable HSTS (security).",
            "Add <title> and meta description where missing (SEO).",
            "Compress large images; defer non-critical JS (performance).",
        ]
        # Short term (1–4 weeks)
        st = [
            "Implement caching headers & CDN for static assets.",
            "Add structured data (Schema.org) for key templates.",
            "Improve heading hierarchy (single H1) and ALT completeness.",
        ]
        # Long term (1–3 months)
        lt = [
            "Integrate Lighthouse/PSI for CWV & lab metrics automation.",
            "Refactor large JS/CSS bundles; adopt code splitting.",
            "Run accessibility audit (WCAG AA) across key user journeys.",
        ]

        def bullets(title: str, items: List[str]):
            elems.append(Paragraph(title, self.styles['H2']))
            for it in items:
                elems.append(Paragraph(f"• {it}", self.styles['Normal']))
            elems.append(Spacer(1, 0.08*inch))

        bullets("Immediate Fixes (0–7 Days)", imm)
        bullets("Short Term (1–4 Weeks)", st)
        bullets("Long Term (1–3 Months)", lt)

        elems.append(Paragraph("Estimated Impact: performance +10–25 points, SEO +10–20 points, risk level ↓1 tier after core fixes.", self.styles['Note']))
        elems.append(PageBreak())

    def scoring_methodology_section(self, elems: List[Any]):
        elems.append(self._section_title("Scoring Methodology"))
        elems.append(Paragraph(
            "Scores are computed from the runner’s heuristics and weights. "
            "Example weight distribution used by the runner: SEO (35%), Performance (35%), Links (20%), Security (10%). "
            "Overall = Σ(category_score × weight).",
            self.styles['Normal'])
        )
        elems.append(Spacer(1, 0.08*inch))
        rows = [
            ["Category", "Weight"],
            ["SEO", "35%"],
            ["Performance", "35%"],
            ["Links", "20%"],
            ["Security", "10%"],
        ]
        elems.append(self._table(rows, colWidths=[3.1*inch, 3.2*inch]))
        elems.append(Paragraph(
            "Transparency: This PDF reflects the exact values the runner provided; fields not available are marked as N/A.",
            self.styles['Note'])
        )
        elems.append(PageBreak())

    def appendix_section(self, elems: List[Any]):
        elems.append(self._section_title("Appendix (Technical Details)"))

        # Dynamic KV/cards derived from runner
        dynamic = self.data.get("dynamic", {})
        cards = dynamic.get("cards", [])
        kv = dynamic.get("kv", [])
        if cards:
            elems.append(Paragraph("Summary Cards", self.styles['H2']))
            for c in cards:
                elems.append(Paragraph(f"<b>{c.get('title','')}</b>: {c.get('body','')}", self.styles['Normal']))
        if kv:
            elems.append(Spacer(1, 0.08*inch))
            elems.append(Paragraph("Key-Value Diagnostics", self.styles['H2']))
            rows = [["Key", "Value"]]
            for pair in kv[:60]:
                rows.append([str(pair.get("key","")), str(pair.get("value",""))])
            elems.append(self._table(rows, colWidths=[2.6*inch, 3.7*inch], fontsize=8))

        elems.append(Spacer(1, 0.08*inch))
        elems.append(Paragraph(
            "Raw HTTP headers, DOM tree, script/CSS inventories, and third-party requests are not captured by the runner "
            "and therefore shown as N/A here. Integrate a headless fetcher and inventory step to populate these fields.",
            self.styles['Note'])
        )
        elems.append(PageBreak())

    def conclusion_section(self, elems: List[Any]):
        elems.append(self._section_title("Conclusion"))
        elems.append(Paragraph(
            "This audit identifies structural, performance, and security improvements required to align the website with "
            "modern web standards and search engine best practices. Addressing the highlighted critical issues will "
            "significantly improve visibility, performance, and risk posture.",
            self.styles['Normal'])
        )
        elems.append(Spacer(1, 0.1*inch))
        elems.append(Paragraph(
            f"Timestamp: {self.audit_dt} — Digital Integrity (SHA-256): {self.integrity}",
            self.styles['Tiny'])
        )

    # ------------- build -------------
    def build_pdf_bytes(self) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
        )
        elems: List[Any] = []
        self.cover_page(elems)
        self.toc_page(elems)
        self.executive_summary(elems)
        self.website_overview(elems)
        self.seo_section(elems)
        self.performance_section(elems)
        self.security_section(elems)
        self.accessibility_section(elems)
        self.ux_section(elems)
        self.broken_links_section(elems)
        self.analytics_tracking_section(elems)
        self.critical_issues_section(elems)
        self.recommendations_section(elems)
        self.scoring_methodology_section(elems)
        self.appendix_section(elems)
        self.conclusion_section(elems)
        doc.build(elems, onFirstPage=self._footer, onLaterPages=self._footer)
        return buf.getvalue()

# ------------------------------------------------------------
# RUNNER ENTRY POINT
# ------------------------------------------------------------
def generate_audit_pdf(audit_data: Dict[str, Any]) -> bytes:
    """
    Runner-facing function. Accepts the dict produced by runner_result_to_audit_data(...)
    and returns raw PDF bytes (runner writes to file).
    """
    report = PDFReport(audit_data)
    return report.build_pdf_bytes()
``
