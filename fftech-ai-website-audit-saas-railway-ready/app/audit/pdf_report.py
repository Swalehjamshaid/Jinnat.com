# -*- coding: utf-8 -*-
"""
app/audit/pdf_report.py
Enterprise PDF generator (ReportLab) for WebsiteAuditRunner results.
- Consumes dict produced by runner_result_to_audit_data(...) in app/audit/runner.py
- Returns raw PDF bytes (for runner to write to disk)
- No network calls; safe for Railway
- Charts rendered via matplotlib (Agg)

IMPROVEMENTS (backward-compatible; optional data-aware):
  • Real CWV/Lighthouse rendering (if provided by runner)
  • Homepage screenshot (What We Audited page)
  • Accessibility depth (axe-core summary)
  • Mobile-first checks
  • Robots.txt & sitemap & schema display
  • Security depth with CSP analysis, cookies, mixed content, security.txt
  • ROI-prioritized recommendations (Impact/Effort)
  • Executive one-pager (gauges, trend arrows)
  • Crawl summary (if provided)
  • Visual proof of issues (optional screenshots)
  • Extended metrics noise filtering improved
  • Scoring consistency (weights include Accessibility) with formula transparency
  • Cover-page overlap fix, KeepTogether groups, repeating table headers
  • Watermark + PDF metadata
"""
from __future__ import annotations
import io
import os
import re
import json
import socket
import hashlib
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple, Iterable
from urllib.parse import urlparse
from html import escape

# ReportLab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
)
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Charts
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ------------------------------------------------------------
# BRANDING / COLORS / ENV
# ------------------------------------------------------------
PDF_BRAND_NAME = os.getenv("PDF_BRAND_NAME", "FF Tech")
PDF_LOGO_PATH = os.getenv("PDF_LOGO_PATH", "")
SAAS_NAME = os.getenv("PDF_REPORT_TITLE", "Website Audit Report")

PRIMARY_DARK   = colors.HexColor("#1A2B3C")
PRIMARY        = colors.HexColor("#2C3E50")
ACCENT_BLUE    = colors.HexColor("#3498DB")
ACCENT_INDIGO  = colors.HexColor("#3F51B5")
SUCCESS_GREEN  = colors.HexColor("#27AE60")
CRITICAL_RED   = colors.HexColor("#C0392B")
WARNING_ORANGE = colors.HexColor("#F39C12")
MUTED_GREY     = colors.HexColor("#7F8C8D")
PURPLE         = colors.HexColor("#8E44AD")
TEAL           = colors.HexColor("#16A085")
YELLOW         = colors.Color(0.98, 0.91, 0.40)
PALE_BLUE      = colors.HexColor("#EAF2F8")
PALE_GREEN     = colors.HexColor("#EAF7F1")
PALE_YELLOW    = colors.HexColor("#FFF9E6")
PALE_RED       = colors.HexColor("#FDEDEC")
LIGHT_GRAY_BG  = colors.HexColor("#F7F9FB")

PALETTE = ['#2E86C1', '#1ABC9C', '#C0392B', '#8E44AD', '#F39C12', '#16A085', '#9B59B6', '#2ECC71']

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

def _safe_get(d: dict, path: List[str], default: Any = "N/A") -> Any:
    cur = d
    try:
        for k in path:
            if not isinstance(cur, dict):
                return default
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

def _float_or(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default

def _bool_to_yesno(v: Any) -> str:
    return "Yes" if bool(v) else "No"

def _risk_from_score(overall: int) -> str:
    try:
        o = int(overall)
    except Exception:
        o = 0
    if o >= 85: return "Low"
    if o >= 70: return "Medium"
    if o >= 50: return "High"
    return "Critical"

def _hash_integrity(audit_data: dict) -> str:
    raw = json.dumps(audit_data, sort_keys=True, ensure_ascii=False).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest().upper()

def _short_id_from_hash(h: str) -> str:
    return h[:12]

def _color_for_priority(priority: str):
    p = (priority or "").lower()
    if ("🔴" in (priority or "")) or (p == "critical"):
        return CRITICAL_RED
    if ("🟠" in (priority or "")) or (p == "high"):
        return WARNING_ORANGE
    if ("🟡" in (priority or "")) or (p == "medium"):
        return YELLOW
    return SUCCESS_GREEN

def _chip(text: str, bg, fg=colors.whitesmoke, pad_x=4, pad_y=2) -> Table:
    t = Table([[Paragraph(escape(text), ParagraphStyle('chip', fontSize=8, textColor=fg))]],
              style=[
                  ('BACKGROUND', (0,0), (-1,-1), bg),
                  ('LEFTPADDING', (0,0), (-1,-1), pad_x),
                  ('RIGHTPADDING', (0,0), (-1,-1), pad_x),
                  ('TOPPADDING', (0,0), (-1,-1), pad_y),
                  ('BOTTOMPADDING', (0,0), (-1,-1), pad_y),
                  ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                  ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                  ('BOX', (0,0), (-1,-1), 0, bg),
              ])
    return t

def _zebra_table(
    rows: List[List[Any]],
    colWidths: Optional[List[float]] = None,
    header_bg=ACCENT_BLUE,
    header_fg=colors.whitesmoke,
    fontsize=9,
    row_stripe=(colors.whitesmoke, colors.HexColor("#FBFBFB"))
) -> Table:
    t = Table(rows, colWidths=colWidths, hAlign='LEFT', repeatRows=1)
    style = [
        ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0,0), (-1,0), header_bg),
        ('TEXTCOLOR', (0,0), (-1,0), header_fg),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), fontsize),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('REPEATROWS', (0,0), (-1,0)),
    ]
    for i in range(1, len(rows)):
        bg = row_stripe[i % 2]
        style.append(('BACKGROUND', (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style))
    return t

def _chunk(seq: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(seq), size):
        yield seq[i:i+size]

# ---- NEW: scoring helpers (consistent overall) ----
DEFAULT_WEIGHTS = {
    "seo": 0.30,
    "performance": 0.35,
    "security": 0.10,
    "accessibility": 0.15,
    "ux": 0.05,
    "links": 0.05
}

def _recalc_overall_score(scores: Dict[str, Any], weights: Optional[Dict[str, float]] = None) -> int:
    w = dict(DEFAULT_WEIGHTS)
    if isinstance(weights, dict):
        w.update({k: float(v) for k, v in weights.items() if k in w})
    total = 0.0
    for k, weight in w.items():
        total += _int_or(scores.get(k, 0), 0) * weight
    return int(round(total))

# ---- NEW: assets loader for homepage + issue screenshots ----
def _load_image_from_assets_path_or_b64(path: Optional[str], b64: Optional[str]) -> Optional[io.BytesIO]:
    if b64:
        try:
            import base64
            raw = base64.b64decode(b64)
            return io.BytesIO(raw)
        except Exception:
            return None
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return io.BytesIO(f.read())
        except Exception:
            return None
    return None

def _load_homepage_screenshot(assets: Dict[str, Any]) -> Optional[io.BytesIO]:
    if not isinstance(assets, dict):
        return None
    return _load_image_from_assets_path_or_b64(
        assets.get("homepage_screenshot_path"),
        assets.get("homepage_screenshot_b64")
    )

def _load_issue_screenshots(assets: Dict[str, Any]) -> List[Tuple[str, io.BytesIO]]:
    out: List[Tuple[str, io.BytesIO]] = []
    if not isinstance(assets, dict):
        return out
    items = assets.get("issue_screenshots", []) or []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title","")) or "Issue"
        buf = _load_image_from_assets_path_or_b64(it.get("path"), it.get("b64"))
        if buf:
            out.append((title, buf))
    # Backward-compatible single alt-issues screenshot
    single = _load_image_from_assets_path_or_b64(assets.get("alt_issues_screenshot_path"), assets.get("alt_issues_screenshot_b64"))
    if single:
        out.append(("Alt Text Issues (examples)", single))
    return out

# ---- NEW: formatters for metrics ----
def _ms(v: Any) -> str:
    x = _int_or(v, -1)
    return f"{x} ms" if x >= 0 else "N/A"

def _pct(v: Any) -> str:
    try:
        return f"{float(v):.0f}"
    except Exception:
        return "N/A"

def _perf_color(score: Optional[float]):
    try:
        s = float(score)
    except Exception:
        return MUTED_GREY
    if s >= 90: return SUCCESS_GREEN
    if s >= 50: return WARNING_ORANGE
    return CRITICAL_RED

# ---- NEW: CSP analyzer ----
def _analyze_csp(csp: str) -> Dict[str, Any]:
    if not isinstance(csp, str) or not csp:
        return {"present": False}
    lower = csp.lower()
    return {
        "present": True,
        "unsafe_inline": "'unsafe-inline'" in lower,
        "unsafe_eval": "'unsafe-eval'" in lower,
        "allows_data": "data:" in lower,
        "allows_http": "http:" in lower and "upgrade-insecure-requests" not in lower,
        "has_default_src": "default-src" in lower,
    }

# ------------------------------------------------------------
# ISSUE DERIVATION — no network calls
# ------------------------------------------------------------
def derive_critical_issues(audit: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    br = audit.get("breakdown", {})
    # Security
    sec = br.get("security", {})
    if isinstance(sec, dict):
        if not sec.get("https", True):
            issues.append({
                "priority": "🔴 Critical",
                "issue": "Site is served over HTTP (no TLS).",
                "category": "Security",
                "impact": "High data interception risk; user trust loss.",
                "fix": "Install TLS certificate and force HTTPS site-wide (HSTS)."
            })
        code = _int_or(sec.get("status_code", 200), 200)
        if code >= 400 or code == 0:
            issues.append({
                "priority": "🟠 High",
                "issue": f"Non-OK status code ({code}).",
                "category": "Security",
                "impact": "Service reliability issues; broken experience.",
                "fix": "Ensure main document returns 200; fix server/app errors."
            })
        if sec.get("https", False) and not sec.get("hsts", False):
            issues.append({
                "priority": "🟡 Medium",
                "issue": "HSTS header not detected.",
                "category": "Security",
                "impact": "HTTPS downgrade risk on some clients.",
                "fix": "Enable Strict-Transport-Security with preload where appropriate."
            })
    # Performance
    perf = br.get("performance", {})
    if isinstance(perf, dict):
        pex = perf.get("extras", {})
        load_ms = _int_or(pex.get("load_ms", 0), 0)
        size_b = _int_or(pex.get("bytes", 0), 0)
        if load_ms > 3000:
            issues.append({
                "priority": "🟠 High" if load_ms > 5000 else "🟡 Medium",
                "issue": f"High load time ({load_ms} ms).",
                "category": "Performance",
                "impact": "Conversion loss; poor UX & Core Web Vitals risk.",
                "fix": "Optimize TTFB, compress assets, lazy-load images, defer non-critical JS."
            })
        if size_b > 1_500_000:
            issues.append({
                "priority": "🟡 Medium",
                "issue": f"Large page size ({_kb(size_b)}).",
                "category": "Performance",
                "impact": "Slower loads on mobile/slow networks; bounce risk.",
                "fix": "Compress images (WebP/AVIF), minify/split JS/CSS, remove unused libs."
            })
    # SEO + Accessibility
    seo = br.get("seo", {})
    if isinstance(seo, dict):
        ex = seo.get("extras", {})
        if not ex.get("title"):
            issues.append({
                "priority": "🔴 Critical",
                "issue": "Missing <title> tag.",
                "category": "SEO",
                "impact": "Poor indexing & SERP CTR.",
                "fix": "Add keyword-optimized title (~55–60 chars) per page."
            })
        if _int_or(ex.get("h1_count", 0), 0) == 0:
            issues.append({
                "priority": "🟠 High",
                "issue": "Missing H1 heading.",
                "category": "SEO",
                "impact": "Weak topical clarity & accessibility.",
                "fix": "Add a single, descriptive H1 targeting the primary keyword."
            })
        imgs_missing = _int_or(ex.get("images_missing_alt", 0), 0)
        imgs_total = _int_or(ex.get("images_total", 0), 0)
        if imgs_missing > 0:
            issues.append({
                "priority": "🟡 Medium" if imgs_missing < 10 else "🟠 High",
                "issue": f"Images missing ALT text ({imgs_missing}/{imgs_total}).",
                "category": "Accessibility",
                "impact": "Screen readers can’t interpret visuals; compliance risk.",
                "fix": "Add descriptive alt text to all meaningful images."
            })
    priority_weight = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Medium": 2, "🟢 Low": 3}
    issues.sort(key=lambda x: priority_weight.get(x["priority"], 9))
    return issues[:12]

# ------------------------------------------------------------
# CHARTS
# ------------------------------------------------------------
def _radar_chart(scores: Dict[str, Any]) -> io.BytesIO:
    order = ["seo", "performance", "security", "accessibility", "ux", "links"]
    labels, values = [], []
    for k in order:
        if k in scores:
            labels.append(k.upper())
            try:
                values.append(int(scores[k]))
            except Exception:
                values.append(0)
    if not labels:
        labels, values = ["SCORE"], [int(scores.get("overall", 0))]
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(4.8, 4.8), subplot_kw=dict(polar=True))
    ax.fill(angles, values, color='#3498DB', alpha=0.28)
    ax.plot(angles, values, color='#2980B9', linewidth=2.2)
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9, fontweight='bold', color='#2C3E50')
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf

def _bar_chart(scores: Dict[str, Any]) -> io.BytesIO:
    cats = [k for k in ["seo", "performance", "security", "accessibility", "ux", "links"] if k in scores]
    vals = [int(scores.get(c, 0)) for c in cats] or [int(scores.get("overall", 0))]
    names = [c.upper() for c in cats] or ["OVERALL"]
    palette = PALETTE[:len(names)]
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    bars = ax.bar(names, vals, color=palette, edgecolor='#2C3E50')
    ax.set_ylim(0, 100)
    ax.set_ylabel('Score', color='#2C3E50')
    ax.set_title('Category Scores', color='#2C3E50', fontsize=10, pad=6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, v + 1, f"{v}", ha='center', fontsize=8, color='#2C3E50')
    ax.spines[['top','right']].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf

def _donut_overall(overall: int) -> io.BytesIO:
    risk = _risk_from_score(overall)
    color = {'Low': '#27AE60', 'Medium': '#F39C12', 'High': '#E67E22', 'Critical': '#C0392B'}[risk]
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    val = max(min(int(overall), 100), 0)
    vals = [val, 100 - val]
    ax.pie(vals, colors=[color, '#ECF0F1'], startangle=90, counterclock=False, wedgeprops={'width':0.42, 'edgecolor':'white'})
    ax.text(0, 0, f"{val}\n/100", ha='center', va='center', fontsize=12, color='#2C3E50')
    ax.set_title('Overall Health', color='#2C3E50', fontsize=10, pad=6)
    plt.axis('equal')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf

# ------------------------------------------------------------
# METRICS FLATTENING
# ------------------------------------------------------------
def _flatten_pairs_from_dict(d: Dict[str, Any], prefix: str = "") -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if not isinstance(d, dict):
        return out

    def _walk(obj: Any, path: List[str]):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v, path + [str(k)])
        elif isinstance(obj, (list, tuple)):
            if len(obj) <= 6 and all(not isinstance(x, (dict, list, tuple)) for x in obj):
                key = ".".join(path)
                out.append((key, ", ".join(map(lambda x: str(x), obj))))
            else:
                key = ".".join(path)
                out.append((key, f"List[{len(obj)}]"))
        else:
            key = ".".join(path)
            s = str(obj)
            if len(s) > 300:
                s = s[:297] + "…"
            out.append((key, s))
    _walk(d, [prefix] if prefix else [])
    return [(k.lstrip("."), v) for k, v in out]

def _collect_extended_metrics(audit: Dict[str, Any]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []

    for k in ["audited_url", "website_name", "client_name", "brand_name", "audit_datetime", "overall_score"]:
        if k in audit:
            pairs.append((k, str(audit.get(k))))

    sc = audit.get("scores", {})
    if isinstance(sc, dict):
        for k, v in sc.items():
            pairs.append((f"scores.{k}", str(v)))

    # Optional integrations (lighthouse/accessibility/robots/sitemap/schema/security/mobile/benchmarks/assets/crawl/competitors)
    for key in ["lighthouse", "accessibility", "robots", "sitemap", "structured_data",
                "security_deep", "mobile", "benchmarks", "assets", "crawl", "competitors"]:
        block = audit.get(key, {})
        if isinstance(block, dict) and block:
            pairs += _flatten_pairs_from_dict(block, key)

    br = audit.get("breakdown", {})
    if isinstance(br, dict):
        pairs += _flatten_pairs_from_dict(br, "breakdown")

    dy = audit.get("dynamic", {})
    if isinstance(dy, dict):
        cards = dy.get("cards", [])
        kv = dy.get("kv", [])
        if isinstance(cards, list):
            for i, c in enumerate(cards):
                title = str(c.get('title',''))
                body = str(c.get('body',''))
                if title or body:
                    pairs.append((f"dynamic.cards[{i}].title", title))
                    pairs.append((f"dynamic.cards[{i}].body", body))
        if isinstance(kv, list):
            for p in kv:
                k = str(p.get("key",""))
                v = str(p.get("value",""))
                if k:
                    pairs.append((f"dynamic.kv.{k}", v))

    # Deduplicate by key
    seen = set()
    deduped: List[Tuple[str, str]] = []
    for k,v in pairs:
        if k not in seen:
            seen.add(k)
            deduped.append((k,v))

    # Stronger noise filtering
    filtered = []
    noisy_substrings = [
        "<!doctype", "<html", "script", "base64,", "data:image/", "function(", "{", "}", "[object",
        "charset=", " style=", " class=", "<svg", "</svg"
    ]
    for k, v in deduped:
        v_low = str(v).lower()
        if any(s in v_low for s in noisy_substrings):
            continue
        filtered.append((k, v))
    return filtered

# ------------------------------------------------------------
# PDF GENERATOR
# ------------------------------------------------------------
class PDFReport:
    def __init__(self, audit: Dict[str, Any]):
        self.data = audit

        # Optional custom font (fallback to Helvetica)
        font_path = os.getenv("PDF_FONT_PATH", "")
        try:
            if font_path and os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont("BrandSans", font_path))
                base_font = "BrandSans"
            else:
                base_font = "Helvetica"
        except Exception:
            base_font = "Helvetica"

        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle('Muted', fontSize=8, textColor=MUTED_GREY, leading=11, fontName=base_font))
        self.styles.add(ParagraphStyle('H2', parent=self.styles['Heading2'], textColor=PRIMARY_DARK, fontName=base_font))
        self.styles.add(ParagraphStyle('H3', parent=self.styles['Heading3'], textColor=PRIMARY_DARK, fontName=base_font))
        self.styles.add(ParagraphStyle('Note', fontSize=9, textColor=MUTED_GREY, leading=12, fontName=base_font))
        self.styles.add(ParagraphStyle('Tiny', fontSize=7, textColor=MUTED_GREY, fontName=base_font))
        self.styles.add(ParagraphStyle('Brand', fontSize=24, textColor=PRIMARY_DARK, fontName=base_font))
        self.styles.add(ParagraphStyle('ReportTitle', fontSize=18, leading=22, textColor=PRIMARY_DARK, fontName=base_font))
        self.styles.add(ParagraphStyle('Caption', fontSize=8, textColor=MUTED_GREY, leading=10, fontName=base_font))
        self.styles.add(ParagraphStyle('KPI', fontSize=10, textColor=PRIMARY, leading=12, fontName=base_font))

        # Integrity & IDs
        self.integrity = _hash_integrity(audit)
        self.report_id = _short_id_from_hash(self.integrity)

        # Header fields
        self.brand = audit.get("brand_name", PDF_BRAND_NAME) or PDF_BRAND_NAME
        self.client = audit.get("client_name", "N/A")
        self.url = audit.get("audited_url", "N/A")
        self.site_name = audit.get("website_name", self.url)
        self.audit_dt = audit.get("audit_datetime", _now_str())

        # Scores
        self.scores = dict(audit.get("scores", {}))
        self.scores.setdefault("overall", _int_or(audit.get("overall_score", 0), 0))
        self.scores.setdefault("accessibility", _int_or(_safe_get(audit, ["breakdown", "accessibility", "score"], 0), 0))
        self.scores.setdefault("ux", _int_or(_safe_get(audit, ["breakdown", "ux", "score"], 0), 0))
        self.scores.setdefault("links", _int_or(_safe_get(audit, ["breakdown", "links", "score"], 0), 0))

        # Weights + consistent overall
        self.weights = audit.get("weights", None)
        self.runner_overall = _int_or(self.scores.get("overall", audit.get("overall_score", 0)), 0)
        self.computed_overall = _recalc_overall_score(self.scores, self.weights or None)
        self.overall = self.computed_overall
        self.risk = _risk_from_score(self.overall)

        # Derived issues
        self.issues = derive_critical_issues(self.data)

        # Overview
        host = _hostname(self.url)
        perf_extras = _safe_get(self.data, ["breakdown", "performance", "extras"], {})
        self.overview = {
            "domain": host or "N/A",
            "ip": _get_ip(host) if host else "Unknown",
            "hosting_provider": "N/A (not detected)",
            "server_location": "N/A (GeoIP not integrated)",
            "cms": "Custom/Unknown",
            "ssl_status": "HTTPS" if _safe_get(self.data, ["breakdown", "security"]).get("https", False) else "HTTP",
            "http_to_https": "N/A",
            "load_ms": _int_or(perf_extras.get("load_ms", 0), 0),
            "page_size": _kb(_int_or(perf_extras.get("bytes", 0), 0)),
            "total_requests_approx": int(
                _int_or(perf_extras.get("scripts", 0), 0)
                + _int_or(perf_extras.get("styles", 0), 0)
                + 1
            ),
        }

        # Optional integrations
        self.lh = audit.get("lighthouse", {}) if isinstance(audit.get("lighthouse", {}), dict) else {}
        self.a11y = audit.get("accessibility", {}) if isinstance(audit.get("accessibility", {}), dict) else {}
        self.mobile = audit.get("mobile", {}) if isinstance(audit.get("mobile", {}), dict) else {}
        self.robots = audit.get("robots", {}) if isinstance(audit.get("robots", {}), dict) else {}
        self.sitemap = audit.get("sitemap", {}) if isinstance(audit.get("sitemap", {}), dict) else {}
        self.schema = audit.get("structured_data", {}) if isinstance(audit.get("structured_data", {}), dict) else {}
        self.secdeep = audit.get("security_deep", {}) if isinstance(audit.get("security_deep", {}), dict) else {}
        self.assets = audit.get("assets", {}) if isinstance(audit.get("assets", {}), dict) else {}
        self.bench = audit.get("benchmarks", {}) if isinstance(audit.get("benchmarks", {}), dict) else {}
        self.history = audit.get("history", []) if isinstance(audit.get("history", []), list) else []
        self.crawl = audit.get("crawl", {}) if isinstance(audit.get("crawl", {}), dict) else {}
        self.competitors = audit.get("competitors", {}) if isinstance(audit.get("competitors", {}), dict) else {}

    # --------------------- page decorators ---------------------
    def _watermark(self, canvas: Canvas):
        try:
            canvas.saveState()
            canvas.setFillColor(colors.Color(0.1, 0.1, 0.2, alpha=0.04))
            canvas.setFont('Helvetica', 48)
            canvas.translate(A4[0]/2, A4[1]/2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, f"{self.brand} • Confidential")
        finally:
            canvas.restoreState()

    def _footer(self, canvas: Canvas, doc):
        self._watermark(canvas)
        canvas.saveState()
        canvas.setFillColor(ACCENT_INDIGO)
        canvas.rect(0, 0.45*inch, A4[0], 0.02*inch, fill=1, stroke=0)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(PRIMARY_DARK)
        canvas.drawString(inch, 0.28*inch, f"{self.brand} | Integrity: {self.integrity[:16]}…")
        canvas.drawRightString(A4[0]-inch, 0.28*inch, f"Page {doc.page}")
        if doc.page == 1:
            try:
                canvas.setTitle(f"{self.site_name} – Website Audit Report")
                canvas.setAuthor(self.brand)
                canvas.setSubject("Website Performance, Accessibility, Security & SEO Audit")
                canvas.setKeywords("Core Web Vitals, Lighthouse, Accessibility, Security, SEO, Audit, PDF")
            except Exception:
                pass
        canvas.restoreState()

    def _table(self, rows: List[List[Any]], colWidths: Optional[List[float]] = None,
               header_bg=colors.whitesmoke, fontsize=9):
        return _zebra_table(rows, colWidths, header_bg=header_bg, fontsize=fontsize)

    def _section_title(self, text: str) -> Paragraph:
        return Paragraph(escape(text), self.styles['Heading1'])

    # --------------------- sections ---------------------
    def cover_page(self, elems: List[Any]):
        block: List[Any] = []
        block.append(Spacer(1, 0.55*inch))

        if isinstance(PDF_LOGO_PATH, str) and PDF_LOGO_PATH and os.path.exists(PDF_LOGO_PATH):
            try:
                block.append(Image(PDF_LOGO_PATH, width=1.6*inch, height=1.6*inch))
                block.append(Spacer(1, 0.2*inch))
            except Exception:
                pass
        else:
            block.append(_chip(self.brand, ACCENT_INDIGO))
            block.append(Spacer(1, 0.15*inch))

        block.append(Paragraph(self.brand.upper(), self.styles['Brand']))
        block.append(Paragraph("Website Performance & Compliance Dossier", self.styles['ReportTitle']))
        block.append(Spacer(1, 0.25*inch))

        kpi_row = [
            [_chip(f"Risk: {self.risk}", {'Low': SUCCESS_GREEN, 'Medium': WARNING_ORANGE, 'High': colors.HexColor('#E67E22'), 'Critical': CRITICAL_RED}[self.risk])],
            [_chip(f"Overall: {self.overall}/100", ACCENT_BLUE)]
        ]
        kpi_tbl = Table(kpi_row, colWidths=[2.0*inch], hAlign='LEFT')
        kpi_tbl.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        block.append(kpi_tbl)
        block.append(Spacer(1, 0.18*inch))

        rows = [
            ["Website URL Audited", self.url],
            ["Audit Date & Time", self.audit_dt],
            ["Report ID", self.report_id],
            ["Generated By", SAAS_NAME],
        ]
        block.append(self._table(rows, colWidths=[2.3*inch, 3.8*inch], header_bg=PALE_BLUE))
        block.append(Spacer(1, 0.16*inch))
        notice = ("This report contains confidential and proprietary information intended solely for the recipient. "
                  "Unauthorized distribution is prohibited.")
        block.append(Paragraph(notice, self.styles['Muted']))

        elems.append(KeepTogether(block))
        elems.append(PageBreak())

    def toc_page(self, elems: List[Any]):
        elems.append(self._section_title("Contents"))
        bullets_list = [
            "Executive Summary",
            "Executive Highlights",
            "What We Audited (Homepage Snapshot)",
            "Website Overview",
            "SEO Audit",
            "Performance Audit",
            "Security Audit",
            "Accessibility Audit",
            "User Experience (UX) & Mobile",
            "Crawl Summary (if available)",
            "Visual Proof of Issues (if available)",
            "Broken Link Analysis",
            "Analytics & Tracking",
            "Critical Issues Summary",
            "Recommendations & Fix Roadmap",
            "Scoring Methodology",
            "Extended Metrics (Auto-Expanded)",
            "Appendix (Technical Details)",
            "Conclusion",
        ]
        for b in bullets_list:
            elems.append(Paragraph(f"• {escape(b)}", self.styles['Normal']))
        elems.append(Spacer(1, 0.1*inch))
        elems.append(Paragraph("Note: Page numbers are included in the footer.", self.styles['Muted']))
        elems.append(PageBreak())

    def executive_summary(self, elems: List[Any]):
        elems.append(self._section_title("Executive Health Summary"))

        # Charts grid: Radar | Bar | Donut
        radar = Image(_radar_chart(self.scores), width=2.8*inch, height=2.8*inch)
        bars  = Image(_bar_chart(self.scores),   width=3.0*inch, height=2.2*inch)
        donut = Image(_donut_overall(self.overall), width=2.0*inch, height=2.0*inch)
        grid = Table([[radar, Table([[bars],[donut]], style=[('ALIGN',(0,0),(-1,-1),'CENTER')])]],
                     colWidths=[3.0*inch, 3.1*inch])
        grid.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elems.append(grid)
        # Alt-like captions (assistive context)
        elems.append(Paragraph(
            "Chart captions: Radar shows category distribution; Bar shows individual category scores; "
            "Donut shows computed overall score based on weighted categories.",
            self.styles['Caption'])
        )
        elems.append(Spacer(1, 0.12*inch))

        krows = [["Overall Website Health (computed)", f"{self.overall}/100"]]
        if self.runner_overall != self.overall:
            krows.append(["Overall (runner provided)", f"{self.runner_overall}/100"])
        krows += [
            ["Overall Risk Level", self.risk],
            ["SEO Score", str(_int_or(self.scores.get("seo", 0), 0))],
            ["Performance Score", str(_int_or(self.scores.get("performance", 0), 0))],
            ["Security Score", str(_int_or(self.scores.get("security", 0), 0))],
            ["Accessibility Score", str(_int_or(self.scores.get("accessibility", 0), 0))],
            ["UX Score", str(_int_or(self.scores.get("ux", 0), 0))],
            ["Links Score", str(_int_or(self.scores.get("links", 0), 0))],
        ]
        elems.append(self._table(krows, colWidths=[2.9*inch, 3.4*inch], header_bg=PALE_GREEN))
        elems.append(Spacer(1, 0.05*inch))
        weights_disp = ", ".join([f"{k.upper()} {int(v*100)}%" for k, v in DEFAULT_WEIGHTS.items()])
        elems.append(Paragraph(
            f"Scoring formula: Overall = Σ(category × weight). Defaults → {escape(weights_disp)}. "
            "Runner-supplied weights, if any, override defaults.",
            self.styles['Note']
        ))
        elems.append(Spacer(1, 0.12*inch))

        elems.append(Paragraph("Top Critical Issues & Estimated Business Impact", self.styles['H2']))
        issues = self.issues[:5]
        if not issues:
            elems.append(Paragraph("No critical issues derived from available data.", self.styles['Normal']))
        else:
            rows = [["Priority", "Issue", "Category", "Impact", "Recommended Fix"]]
            for i in issues:
                rows.append([i["priority"], i["issue"], i["category"], i["impact"], i["fix"]])
            t = self._table(rows, colWidths=[0.95*inch, 2.25*inch, 0.9*inch, 1.5*inch, 1.6*inch], header_bg=ACCENT_BLUE, fontsize=8)
            for r in range(1, len(rows)):
                pr = rows[r][0]
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, r), (0, r), _color_for_priority(pr)),
                    ('TEXTCOLOR', (0, r), (0, r), colors.whitesmoke)
                ]))
            elems.append(t)
        elems.append(PageBreak())

    def executive_one_pager(self, elems: List[Any]):
        elems.append(self._section_title("Executive Highlights"))
        donut_overall = Image(_donut_overall(self.overall), width=2.0*inch, height=2.0*inch)
        cats = ["performance", "seo", "security", "accessibility"]
        smalls = []
        for c in cats:
            val = int(self.scores.get(c, 0))
            img = Image(_donut_overall(val), width=1.5*inch, height=1.5*inch)
            smalls.append(Table([[Paragraph(c.upper(), self.styles['Tiny'])], [img]],
                                style=[('ALIGN',(0,0),(-1,-1),'CENTER')]))
        grid = Table([[donut_overall, Table([smalls[:2], smalls[2:]], style=[('ALIGN',(0,0),(-1,-1),'CENTER')])]],
                     colWidths=[2.5*inch, 3.6*inch])
        grid.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elems.append(grid)
        elems.append(Paragraph("Gauges summarize overall and category health at a glance.", self.styles['Caption']))
        elems.append(Spacer(1, 0.08*inch))

        # Trends with arrows (if history)
        if self.history and len(self.history) >= 2:
            try:
                a, b = self.history[-2], self.history[-1]
                def arrow(curr, prev):
                    try:
                        c, p = float(curr), float(prev)
                        return "↑" if c > p else ("↓" if c < p else "→")
                    except Exception:
                        return "→"
                overall_arrow = arrow(b.get("overall"), a.get("overall"))
                perf_arrow = arrow(b.get("performance"), a.get("performance"))
                rows = [["Date", "Overall", "Δ", "Performance", "Δ"]]
                for h in self.history[-5:]:
                    rows.append([str(h.get("dt","")), str(h.get("overall","")), "", str(h.get("performance","")), ""])
                rows.append(["Latest change", str(b.get("overall","")), overall_arrow, str(b.get("performance","")), perf_arrow])
                elems.append(Paragraph("Recent Trend (Overall / Performance)", self.styles['H2']))
                elems.append(self._table(rows, colWidths=[1.5*inch, 1.2*inch, 0.4*inch, 1.4*inch, 0.4*inch], header_bg=PALE_GREEN))
            except Exception:
                pass
        elems.append(PageBreak())

    def what_we_audited(self, elems: List[Any]):
        elems.append(self._section_title("What We Audited (Homepage Snapshot)"))
        ctx_rows = [["Final URL", str(self.lh.get("final_url", self.url)) if isinstance(self.lh, dict) else self.url]]
        cfg = self.lh.get("config", {}) if isinstance(self.lh, dict) else {}
        if cfg:
            ctx_rows.append(["Device / Form Factor", f"{cfg.get('device','N/A')} / {cfg.get('form_factor','N/A')}"])
        elems.append(self._table(ctx_rows, colWidths=[2.6*inch, 3.7*inch], header_bg=LIGHT_GRAY_BG))
        elems.append(Spacer(1, 0.08*inch))

        # Perf chip (color-coded)
        cats = self.lh.get("categories", {}) if isinstance(self.lh, dict) else {}
        perf_val = cats.get("performance", None)
        perf_chip_bg = _perf_color(perf_val) if perf_val is not None else MUTED_GREY
        elems.append(_chip(f"Lighthouse Performance: {(_pct(perf_val) + '/100') if perf_val is not None else 'N/A'}", perf_chip_bg))
        elems.append(Spacer(1, 0.12*inch))

        img_buf = _load_homepage_screenshot(self.assets)
        if img_buf:
            try:
                elems.append(Image(img_buf, width=5.8*inch, height=3.35*inch))
            except Exception:
                elems.append(Paragraph("Screenshot could not be rendered.", self.styles['Note']))
        else:
            elems.append(Paragraph("No screenshot available. Add assets.homepage_screenshot_path or homepage_screenshot_b64.", self.styles['Note']))
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
        # Benchmarks & competitors (optional)
        if isinstance(self.bench, dict) and self.bench:
            try:
                industry = self.bench.get("industry", "Industry")
                avg = self.bench.get("avg", {})
                bench_line = f"{industry} avg: LCP {_ms(avg.get('LCP_ms'))}, INP {_ms(avg.get('INP_ms', avg.get('INP', None)))}, CLS {str(avg.get('CLS', 'N/A'))}, Perf {str(avg.get('Performance','N/A'))}"
                rows.append(["Benchmark (context)", bench_line])
            except Exception:
                pass
        if isinstance(self.competitors, dict) and self.competitors:
            try:
                comp = self.competitors.get("summary","")
                if comp:
                    rows.append(["Competitor Comparison", str(comp)[:180] + ("…" if len(str(comp))>180 else "")])
            except Exception:
                pass
        elems.append(self._table(rows, colWidths=[2.7*inch, 3.6*inch], header_bg=PALE_BLUE))
        elems.append(PageBreak())

    def seo_section(self, elems: List[Any]):
        elems.append(self._section_title("SEO Audit"))
        seo = _safe_get(self.data, ["breakdown", "seo"], {})
        ex = seo.get("extras", {}) if isinstance(seo, dict) else {}
        title = ex.get("title") or ""
        title_len = len(title)
        meta_desc_present = ex.get("meta_description_present", False)
        canonical = ex.get("canonical") or ""
        h1_count = _int_or(ex.get("h1_count", 0), 0)
        images_total = _int_or(ex.get("images_total", 0), 0)
        images_missing = _int_or(ex.get("images_missing_alt", 0), 0)

        elems.append(Paragraph("On-Page SEO", self.styles['H2']))
        on_rows = [
            ["Title tag (length + optimization)", f"{title_len} chars" if title else "Missing"],
            ["Meta description (length + optimization)", "Present" if meta_desc_present else "Missing"],
            ["H1, H2 structure", f"H1 count: {h1_count}; H2: N/A"],
            ["Canonical tag presence", "Yes" if canonical else "No"],
            ["Image ALT attributes missing", f"{images_missing}/{images_total}"],
        ]
        elems.append(self._table(on_rows, colWidths=[3.1*inch, 3.2*inch], header_bg=PALE_YELLOW))
        elems.append(Spacer(1, 0.08*inch))

        elems.append(Paragraph("Technical SEO", self.styles['H2']))
        tech_rows = [
            ["Robots.txt", "Present" if self.robots.get("exists") else "Missing"],
            ["Robots rules", f"Allows all: {self.robots.get('allows_all', 'N/A')}"],
            ["Sitemap.xml", "Present & Valid" if self.sitemap.get("exists") and self.sitemap.get("valid") else ("Present" if self.sitemap.get("exists") else "Missing")],
            ["Sitemap URLs (approx)", str(self.sitemap.get("url_count","N/A"))],
            ["Structured data detected", _bool_to_yesno(self.schema.get("detected", False))],
            ["Schema types", ", ".join(self.schema.get("items", [])[:6]) or "N/A"],
            ["Schema errors/warnings", ("Errors: " + str(len(self.schema.get("errors", []))) + "; Warnings: " + str(len(self.schema.get("warnings", [])))) if self.schema else "N/A"],
            ["Core Web Vitals (lab)", f"LCP {_ms(self.lh.get('metrics',{}).get('LCP_ms'))}, INP {_ms(self.lh.get('metrics',{}).get('INP_ms'))}, CLS {str(self.lh.get('metrics',{}).get('CLS','N/A'))}"],
            ["Mobile responsiveness", "Viewport OK" if self.mobile.get("viewport_meta") else "Viewport missing"],
        ]
        elems.append(self._table(tech_rows, colWidths=[3.1*inch, 3.2*inch], header_bg=PALE_BLUE))
        elems.append(PageBreak())

    def performance_section(self, elems: List[Any]):
        elems.append(self._section_title("Performance Audit"))
        lh = self.lh if isinstance(self.lh, dict) else {}
        cats = lh.get("categories", {}) if isinstance(lh.get("categories", {}), dict) else {}
        m = lh.get("metrics", {}) if isinstance(lh.get("metrics", {}), dict) else {}
        opps = lh.get("opportunities", []) or []
        diags = lh.get("diagnostics", []) or []
        cfg = lh.get("config", {}) if isinstance(lh.get("config", {}), dict) else {}

        perf_val = cats.get("performance", None)
        perf_chip_bg = _perf_color(perf_val) if perf_val is not None else MUTED_GREY
        elems.append(Table([[_chip(f"Lighthouse Performance: {(_pct(perf_val) + '/100') if perf_val is not None else 'N/A'}", perf_chip_bg)]],
                           colWidths=[6.3*inch], style=[('ALIGN',(0,0),(-1,-1),'LEFT')]))
        elems.append(Spacer(1, 0.08*inch))

        top_rows = [
            ["Device / Form Factor", f"{cfg.get('device','N/A')} / {cfg.get('form_factor','N/A')}"],
            ["Largest Contentful Paint (LCP)", _ms(m.get("LCP_ms"))],
            ["Interaction to Next Paint (INP)", _ms(m.get("INP_ms"))],
            ["Cumulative Layout Shift (CLS)", str(m.get("CLS", "N/A"))],
            ["First Contentful Paint (FCP)", _ms(m.get("FCP_ms"))],
            ["Time to First Byte (TTFB)", _ms(m.get("TTFB_ms"))],
            ["Speed Index", _ms(m.get("SpeedIndex_ms"))],
            ["Total Blocking Time (TBT)", _ms(m.get("TBT_ms"))],
        ]
        elems.append(self._table(top_rows, colWidths=[3.6*inch, 2.7*inch], header_bg=PALE_GREEN))
        elems.append(Paragraph(
            "Interpretation: LCP < 2.5s (good), INP < 200ms (good), CLS < 0.1 (good). Values shown are lab metrics.",
            self.styles['Caption']
        ))
        elems.append(Spacer(1, 0.08*inch))

        elems.append(Paragraph("Opportunities (estimated savings)", self.styles['H2']))
        if opps:
            rows = [["Opportunity", "Est. Savings"]]
            for o in opps[:8]:
                rows.append([str(o.get("title","")), _ms(o.get("estimated_savings_ms"))])
            elems.append(self._table(rows, colWidths=[4.2*inch, 2.1*inch], header_bg=PALE_BLUE))
        else:
            elems.append(Paragraph("No opportunities available.", self.styles['Note']))
        elems.append(Spacer(1, 0.06*inch))

        elems.append(Paragraph("Diagnostics", self.styles['H2']))
        if diags:
            rows = [["Check", "Value/Note"]]
            for d in diags[:10]:
                rows.append([str(d.get("id","")), str(d.get("value",""))])
            elems.append(self._table(rows, colWidths=[2.4*inch, 3.9*inch], header_bg=PALE_YELLOW))
        else:
            elems.append(Paragraph("No diagnostics available.", self.styles['Note']))
        elems.append(PageBreak())

    def security_section(self, elems: List[Any]):
        elems.append(self._section_title("Security Audit"))
        sec = _safe_get(self.data, ["breakdown", "security"], {})
        deep = self.secdeep if isinstance(self.secdeep, dict) else {}
        hdrs = deep.get("headers", {}) if isinstance(deep.get("headers", {}), dict) else {}
        csp_info = _analyze_csp(hdrs.get("content-security-policy", "")) if hdrs else {"present": False}

        # Cookie analysis
        cookies = deep.get("cookies", []) if isinstance(deep.get("cookies", []), list) else []
        insecure = sum(1 for c in cookies if not c.get("secure"))
        no_http_only = sum(1 for c in cookies if not c.get("httpOnly"))
        unknown_same_site = sum(1 for c in cookies if str(c.get("sameSite","Unknown")) == "Unknown")

        rows = [
            ["HTTPS Enabled", _bool_to_yesno(sec.get("https", False)) if isinstance(sec, dict) else "N/A"],
            ["Origin Status Code", str(sec.get("status_code", "N/A")) if isinstance(sec, dict) else "N/A"],
            ["HSTS Enabled?", _bool_to_yesno(sec.get("hsts", False)) if isinstance(sec, dict) else "N/A"],
            ["Content-Security-Policy", "Present" if csp_info.get("present") else "Missing"],
            ["CSP risks", f"unsafe-inline={csp_info.get('unsafe_inline', False)}, unsafe-eval={csp_info.get('unsafe_eval', False)}" if csp_info.get("present") else "N/A"],
            ["Mixed content issues", str(deep.get("mixed_content","N/A"))],
            ["security.txt", "Present" if deep.get("security_txt",{}).get("exists") else "Missing"],
            ["Cookies (sample)", f"{len(cookies)} found; insecure={insecure}, no HttpOnly={no_http_only}, SameSite unknown={unknown_same_site}"],
            ["X-Frame-Options", hdrs.get("x-frame-options", "N/A")],
            ["X-Content-Type-Options", hdrs.get("x-content-type-options","N/A")],
        ]
        elems.append(self._table(rows, colWidths=[3.2*inch, 3.1*inch], header_bg=PALE_RED))
        elems.append(Spacer(1, 0.06*inch))
        elems.append(Paragraph("Tip: Prefer strong CSP without 'unsafe-inline'/'unsafe-eval'. Ensure cookies set Secure/HttpOnly/SameSite.", self.styles['Note']))
        elems.append(PageBreak())

    def accessibility_section(self, elems: List[Any]):
        elems.append(self._section_title("Accessibility Audit"))
        ex = _safe_get(self.data, ["breakdown", "seo", "extras"], {})
        missing_alt = _int_or(ex.get("images_missing_alt", 0), 0)
        imgs_total = _int_or(ex.get("images_total", 0), 0)

        axe = self.a11y.get("axe", {}) if isinstance(self.a11y, dict) else {}
        counts = axe.get("counts", {})
        lvls = axe.get("by_wcag_level", {})
        buckets = axe.get("buckets", {})
        top_issues = axe.get("top_issues", []) or []

        rows1 = [
            ["Missing ALT tags", f"{missing_alt}/{imgs_total}"],
            ["Violations (axe)", str(counts.get("violations","N/A"))],
            ["WCAG Levels (A/AA/AAA)", f"{lvls.get('A','0')}/{lvls.get('AA','0')}/{lvls.get('AAA','0')}"],
            ["Contrast issues", str(buckets.get("color-contrast","N/A"))],
            ["ARIA issues", str(buckets.get("aria","N/A"))],
            ["Keyboard issues", str(buckets.get("keyboard","N/A"))],
            ["Landmarks issues", str(buckets.get("landmarks","N/A"))],
            ["Forms/Labels issues", str(buckets.get("forms","N/A"))],
        ]
        elems.append(self._table(rows1, colWidths=[3.2*inch, 3.1*inch], header_bg=PALE_YELLOW))
        elems.append(Paragraph("WCAG target: 2.2 AA (contrast ≥ 4.5:1, keyboard operability, meaningful order).", self.styles['Caption']))
        elems.append(Spacer(1, 0.06*inch))

        if top_issues:
            elems.append(Paragraph("Top Accessibility Issues (examples)", self.styles['H2']))
            rows2 = [["Rule", "Nodes", "Selectors / Examples"]]
            for t in top_issues[:8]:
                rows2.append([str(t.get("id","")), str(t.get("nodes","")), ", ".join(t.get("examples", [])[:3])])
            elems.append(self._table(rows2, colWidths=[1.8*inch, 0.8*inch, 3.7*inch], header_bg=PALE_BLUE, fontsize=8))
        elems.append(PageBreak())

    def ux_section(self, elems: List[Any]):
        elems.append(self._section_title("User Experience (UX) & Mobile"))
        rows = [
            ["Mobile friendliness", "Viewport OK" if self.mobile.get("viewport_meta") else "Viewport missing"],
            ["Tap targets too small", str(self.mobile.get("tap_targets_small", "N/A"))],
            ["Problematic font sizes", str(self.mobile.get("font_size_issues", "N/A"))],
            ["Layout shift risk (mobile)", str(self.mobile.get("layout_shift_risk", "N/A"))],
            ["CTA visibility", "N/A"],
            ["Navigation clarity", "N/A"],
            ["Form usability", "N/A"],
        ]
        elems.append(self._table(rows, colWidths=[3.2*inch, 3.1*inch], header_bg=PALE_BLUE))
        elems.append(PageBreak())

    def crawl_summary_section(self, elems: List[Any]):
        elems.append(self._section_title("Crawl Summary (If Available)"))
        if not self.crawl:
            elems.append(Paragraph("No crawl data provided by runner.", self.styles['Note']))
            elems.append(PageBreak())
            return
        rows = [
            ["Internal URLs", str(self.crawl.get("internal_urls","N/A"))],
            ["External URLs", str(self.crawl.get("external_urls","N/A"))],
            ["Broken internal links", str(self.crawl.get("broken_internal","N/A"))],
            ["Broken external links", str(self.crawl.get("broken_external","N/A"))],
            ["Max depth crawled", str(self.crawl.get("max_depth","N/A"))],
        ]
        elems.append(self._table(rows, colWidths=[3.2*inch, 3.1*inch], header_bg=LIGHT_GRAY_BG))
        elems.append(PageBreak())

    def visual_proof_section(self, elems: List[Any]):
        elems.append(self._section_title("Visual Proof of Issues"))
        shots = _load_issue_screenshots(self.assets)
        if not shots:
            elems.append(Paragraph("No issue screenshots provided by runner.", self.styles['Note']))
            elems.append(PageBreak())
            return
        for title, buf in shots[:6]:
            elems.append(Paragraph(escape(title), self.styles['H2']))
            try:
                elems.append(Image(buf, width=5.8*inch, height=3.3*inch))
            except Exception:
                elems.append(Paragraph("Screenshot could not be rendered.", self.styles['Note']))
            elems.append(Spacer(1, 0.08*inch))
        elems.append(PageBreak())

    def broken_links_section(self, elems: List[Any]):
        elems.append(self._section_title("Broken Link Analysis"))
        rows = [
            ["URL", "Status Code", "Anchor Text", "Type"],
            ["N/A", "N/A", "N/A", "N/A"]
        ]
        elems.append(self._table(rows, colWidths=[3.0*inch, 0.9*inch, 1.5*inch, 0.9*inch], fontsize=8, header_bg=PALE_RED))
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
        elems.append(self._table(rows, colWidths=[3.2*inch, 3.1*inch], header_bg=PALE_GREEN))
        elems.append(PageBreak())

    def critical_issues_section(self, elems: List[Any]):
        elems.append(self._section_title("Critical Issues Summary"))
        issues = self.issues
        if not issues:
            elems.append(Paragraph("No critical issues derived from available data.", self.styles['Normal']))
            elems.append(PageBreak())
            return
        rows = [["Priority", "Issue", "Category", "Impact", "Recommended Fix"]]
        for i in issues:
            rows.append([i["priority"], i["issue"], i["category"], i["impact"], i["fix"]])
        t = self._table(rows, colWidths=[0.95*inch, 2.25*inch, 0.9*inch, 1.5*inch, 1.6*inch], header_bg=ACCENT_BLUE, fontsize=8)
        for r in range(1, len(rows)):
            pr = rows[r][0]
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, r), (0, r), _color_for_priority(pr)),
                ('TEXTCOLOR', (0, r), (0, r), colors.whitesmoke)
            ]))
        elems.append(t)
        elems.append(PageBreak())

    def recommendations_section(self, elems: List[Any]):
        elems.append(self._section_title("Recommendations & Fix Roadmap"))
        recs = []

        # PSI quick wins
        for o in (self.lh.get("opportunities") or [])[:6] if isinstance(self.lh, dict) else []:
            recs.append({
                "item": f"{o.get('title','')}",
                "impact": "High" if _int_or(o.get("estimated_savings_ms",0),0) >= 800 else "Medium",
                "effort": "Medium",
                "notes": f"Est. savings: {_ms(o.get('estimated_savings_ms'))}"
            })

        # Accessibility
        axe = self.a11y.get("axe", {}) if isinstance(self.a11y, dict) else {}
        if _int_or(axe.get("counts",{}).get("violations",0),0) > 0:
            recs.append({"item":"Resolve contrast & ARIA violations", "impact":"High", "effort":"Medium", "notes":"WCAG 2.2 AA compliance"})

        # Robots/Sitemap
        if not self.robots.get("exists"):
            recs.append({"item":"Add robots.txt", "impact":"Medium", "effort":"Low", "notes":"Basic technical SEO"})
        if not self.sitemap.get("exists"):
            recs.append({"item":"Publish sitemap.xml", "impact":"Medium", "effort":"Low", "notes":"Enable faster discovery"})

        # Security
        if self.secdeep and "content-security-policy" not in (self.secdeep.get("headers") or {}):
            recs.append({"item":"Add CSP header", "impact":"High", "effort":"Medium", "notes":"Mitigate XSS/Injection risk"})
        if self.secdeep and self.secdeep.get("mixed_content",0) > 0:
            recs.append({"item":"Fix mixed content", "impact":"High", "effort":"Low", "notes":"Serve assets via HTTPS only"})

        # Sort by (impact desc, effort asc)
        impact_rank = {"High": 0, "Medium": 1, "Low": 2}
        effort_rank = {"Low": 0, "Medium": 1, "High": 2}
        recs.sort(key=lambda r: (impact_rank.get(r["impact"], 9), effort_rank.get(r["effort"], 9)))

        rows = [["Recommendation", "Impact", "Effort", "Details / Notes"]]
        for r in recs[:12]:
            rows.append([r["item"], r["impact"], r["effort"], r["notes"]])
        elems.append(self._table(rows, colWidths=[2.9*inch, 0.9*inch, 0.9*inch, 2.2*inch], header_bg=ACCENT_BLUE, fontsize=8))
        elems.append(Spacer(1, 0.08*inch))
        elems.append(Paragraph("Prioritized by ROI: (High impact, Low/Medium effort) shown first.", self.styles['Note']))
        elems.append(PageBreak())

    def scoring_methodology_section(self, elems: List[Any]):
        elems.append(self._section_title("Scoring Methodology"))
        w = dict(DEFAULT_WEIGHTS)
        if isinstance(self.weights, dict):
            try:
                w.update({k: float(v) for k, v in self.weights.items() if k in w})
            except Exception:
                pass
        elems.append(Paragraph(
            "Overall = Σ(category score × weight). Weights can be overridden by the runner. "
            "This section shows the effective weights used to compute the displayed Overall score.",
            self.styles['Normal']
        ))
        elems.append(Spacer(1, 0.08*inch))
        rows = [["Category", "Weight"]]
        for k in ["seo","performance","security","accessibility","ux","links"]:
            rows.append([k.upper(), f"{int(w[k]*100)}%"])
        elems.append(self._table(rows, colWidths=[3.2*inch, 3.1*inch], header_bg=PALE_BLUE))
        if self.runner_overall != self.overall:
            elems.append(Paragraph(
                f"Note: Runner provided overall {self.runner_overall}/100 diverged from computed {self.overall}/100. "
                "Displayed charts use the computed score for consistency.",
                self.styles['Note']
            ))
        elems.append(PageBreak())

    def extended_metrics_section(self, elems: List[Any]):
        elems.append(self._section_title("Extended Metrics (Auto-Expanded)"))
        pairs = _collect_extended_metrics(self.data)
        if not pairs:
            elems.append(Paragraph("No additional metrics available from the runner.", self.styles['Normal']))
            elems.append(PageBreak())
            return
        rows = [["Key", "Value"]]
        for k, v in pairs:
            rows.append((k, v))
        header = rows[0]
        data_rows = rows[1:]
        per_table = 36
        for idx, chunk in enumerate(_chunk(data_rows, per_table)):
            tbl_rows = [header] + chunk
            t = self._table(tbl_rows, colWidths=[2.8*inch, 3.5*inch], fontsize=8, header_bg=colors.HexColor("#EEF3FB"))
            elems.append(t)
            if idx < (len(data_rows) - 1) // per_table:
                elems.append(PageBreak())
        elems.append(Spacer(1, 0.08*inch))
        elems.append(Paragraph(
            "Note: Keys are flattened from nested structures (breakdown.*, scores.*, dynamic.*, lighthouse.*, "
            "accessibility.*, robots/sitemap/schema/security_deep/mobile, crawl, competitors).", self.styles['Note']))
        elems.append(PageBreak())

    def appendix_section(self, elems: List[Any]):
        elems.append(self._section_title("Appendix (Technical Details)"))
        dynamic = self.data.get("dynamic", {})
        cards = dynamic.get("cards", [])
        kv = dynamic.get("kv", [])
        if cards:
            elems.append(Paragraph("Summary Cards", self.styles['H2']))
            for c in cards:
                title = str(c.get('title', '') or '')
                body = str(c.get('body', '') or '')
                elems.append(Paragraph(f"<b>{escape(title)}</b>: {escape(body)}", self.styles['Normal']))
        if kv:
            elems.append(Spacer(1, 0.08*inch))
            elems.append(Paragraph("Key-Value Diagnostics", self.styles['H2']))
            rows = [["Key", "Value"]]
            for pair in kv[:120]:
                rows.append([str(pair.get("key", "")), str(pair.get("value", ""))])
            elems.append(self._table(rows, colWidths=[2.8*inch, 3.5*inch], fontsize=8, header_bg=colors.HexColor("#F7F7F7")))
        elems.append(Spacer(1, 0.08*inch))
        elems.append(Paragraph(
            "Raw HTTP headers, DOM tree, script/CSS inventories, and third-party requests are not captured by the runner "
            "and therefore shown as N/A here. Integrate a headless fetcher and inventory step to populate these fields.",
            self.styles['Note']
        ))
        elems.append(PageBreak())

    def conclusion_section(self, elems: List[Any]):
        elems.append(self._section_title("Conclusion"))
        elems.append(Paragraph(
            "This audit identifies structural, performance, and security improvements required to align the website with "
            "modern web standards and search engine best practices. Addressing the highlighted critical issues will "
            "significantly improve visibility, performance, and risk posture.",
            self.styles['Normal']
        ))
        elems.append(Spacer(1, 0.1*inch))
        elems.append(Paragraph(
            f"Timestamp: {self.audit_dt} — Digital Integrity (SHA-256): {self.integrity}",
            self.styles['Tiny']
        ))

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
        self.executive_one_pager(elems)
        self.what_we_audited(elems)
        self.website_overview(elems)
        self.seo_section(elems)
        self.performance_section(elems)
        self.security_section(elems)
        self.accessibility_section(elems)
        self.ux_section(elems)
        self.crawl_summary_section(elems)          # new optional
        self.visual_proof_section(elems)           # new optional
        self.broken_links_section(elems)
        self.analytics_tracking_section(elems)
        self.critical_issues_section(elems)
        self.recommendations_section(elems)
        self.scoring_methodology_section(elems)
        self.extended_metrics_section(elems)
        self.appendix_section(elems)
        self.conclusion_section(elems)
        doc.build(elems, onFirstPage=self._footer, onLaterPages=self._footer)
        return buf.getvalue()

# ------------------------------------------------------------
# RUNNER ENTRY POINT (required by runner.py)
# ------------------------------------------------------------
def generate_audit_pdf(audit_data: Dict[str, Any]) -> bytes:
    """
    Runner-facing function. Accepts the dict produced by runner_result_to_audit_data(...)
    and returns raw PDF bytes (runner writes to file).

    Backward-compatible: no network calls; supports optional enrichment keys:
      audit_data['lighthouse'], audit_data['assets'], audit_data['accessibility']['axe'],
      audit_data['mobile'], audit_data['robots'], audit_data['sitemap'], audit_data['crawl'],
      audit_data['structured_data'], audit_data['security_deep'], audit_data['benchmarks'],
      audit_data['history'], audit_data['competitors']
    """
    report = PDFReport(audit_data)
    return report.build_pdf_bytes()
