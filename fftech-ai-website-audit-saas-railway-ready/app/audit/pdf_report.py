# -*- coding: utf-8 -*-
"""
app/audit/pdf_report.py
Enterprise PDF generator (ReportLab) for WebsiteAuditRunner results.
- Consumes dict produced by runner_result_to_audit_data(...) in app/audit/runner.py
- Returns raw PDF bytes (runner writes to disk)
- No network calls; safe for Railway
- Charts rendered via matplotlib (Agg)

UPGRADES (backward-compatible; optional-data aware):
  • Phase 1: First-page clarity — larger fonts, stronger contrast, wider paddings, divider, softer watermark
  • Phase 2: Remove "N/A" — auto-hide missing rows; show muted note "Fields shown only when data is available from the runner."
  • Phase 3: Real CWV/Lighthouse (if provided), homepage screenshot, axe-core depth, mobile checks, robots/sitemap/schema, security depth
  • Phase 4: ROI-prioritized recommendations (+ Apple-specific hints when domain is apple.com), benchmarking/competitors (if provided)
  • Phase 5: Consistent scoring incl. Accessibility; trend arrows; improved extended-metrics filtering; PDF metadata; captions for charts
  • 2026-02 Improvements: Credibility guards, Core Web Vitals section, industry benchmarks, business impact + ROI, maturity index,
    risk matrix visualization, 30-60-90 roadmap, competitive analysis, optional extended-metrics annex.
"""
from __future__ import annotations
import io
import os
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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether, HRFlowable
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
DIVIDER_GRAY   = colors.HexColor("#DCE3EA")

PALETTE = ['#2E86C1', '#1ABC9C', '#C0392B', '#8E44AD', '#F39C12', '#16A085', '#9B59B6', '#2ECC71']

# ------------------------------------------------------------
# HELPERS (no "N/A" anywhere, avoid impossible values)
# ------------------------------------------------------------
def _now_str() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _get_ip(host: str) -> Optional[str]:
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None


def _kb(n: Any) -> Optional[str]:
    try:
        val = int(n)
        if val <= 0:
            return None
        return f"{round(val/1024.0, 1)} KB"
    except Exception:
        return None


def _safe_get(d: dict, path: List[str], default: Any = None) -> Any:
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


def _risk_from_score(overall: int) -> str:
    try:
        o = int(overall)
    except Exception:
        o = 0
    if o >= 85:
        return "Low"
    if o >= 70:
        return "Medium"
    if o >= 50:
        return "High"
    return "Critical"


def _hash_integrity(audit_data: dict) -> str:
    raw = json.dumps(audit_data, sort_keys=True, ensure_ascii=False).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest().upper()


def _short_id_from_hash(h: str) -> str:
    return h[:12]


def _chip(text: str, bg, fg=colors.whitesmoke, pad_x=8, pad_y=4, font_size=10) -> Table:
    t = Table([[Paragraph(escape(text), ParagraphStyle('chip', fontSize=font_size, textColor=fg))]],
              style=[
                  ('BACKGROUND', (0, 0), (-1, -1), bg),
                  ('LEFTPADDING', (0, 0), (-1, -1), pad_x),
                  ('RIGHTPADDING', (0, 0), (-1, -1), pad_x),
                  ('TOPPADDING', (0, 0), (-1, -1), pad_y),
                  ('BOTTOMPADDING', (0, 0), (-1, -1), pad_y),
                  ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                  ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                  ('BOX', (0, 0), (-1, -1), 0, bg),
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
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('TEXTCOLOR', (0, 0), (-1, 0), header_fg),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), fontsize),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('REPEATROWS', (0, 0), (-1, 0)),
    ]
    for i in range(1, len(rows)):
        bg = row_stripe[i % 2]
        style.append(('BACKGROUND', (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style))
    return t


def _chunk(seq: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


# ---- Scoring (includes Accessibility so overall is consistent)
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


# ---- Assets (homepage + issue screenshots)
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
        title = str(it.get("title", "")) or "Issue"
        buf = _load_image_from_assets_path_or_b64(it.get("path"), it.get("b64"))
        if buf:
            out.append((title, buf))
    single = _load_image_from_assets_path_or_b64(assets.get("alt_issues_screenshot_path"), assets.get("alt_issues_screenshot_b64"))
    if single:
        out.append(("Alt Text Issues (examples)", single))
    return out


# ---- Metric formatters (return None if missing — so rows get hidden)
def _ms(v: Any) -> Optional[str]:
    try:
        x = int(float(v))
        if x <= 0:
            return None  # credibility guard: treat 0 or negative as missing
        return f"{x} ms"
    except Exception:
        return None


def _pct(v: Any) -> Optional[str]:
    try:
        return f"{float(v):.0f}"
    except Exception:
        return None


def _perf_color(score: Optional[float]):
    try:
        s = float(score)
    except Exception:
        return MUTED_GREY
    if s >= 90:
        return SUCCESS_GREEN
    if s >= 50:
        return WARNING_ORANGE
    return CRITICAL_RED


# ---- CSP analyzer
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
                "issue": f"Large page size ({_kb(size_b) or str(size_b)+' bytes'}).",
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
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
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
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v}", ha='center', fontsize=8, color='#2C3E50')
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf


def _donut_overall(overall: int, title: str = 'Overall Health') -> io.BytesIO:
    risk = _risk_from_score(overall)
    color = {'Low': '#27AE60', 'Medium': '#F39C12', 'High': '#E67E22', 'Critical': '#C0392B'}[risk]
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    val = max(min(int(overall), 100), 0)
    vals = [val, 100 - val]
    ax.pie(vals, colors=[color, '#ECF0F1'], startangle=90, counterclock=False,
           wedgeprops={'width': 0.42, 'edgecolor': 'white'})
    ax.text(0, 0, f"{val}\n/100", ha='center', va='center', fontsize=12, color='#2C3E50')
    ax.set_title(title, color='#2C3E50', fontsize=10, pad=6)
    plt.axis('equal')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf


# ------------------------------------------------------------
# METRICS FLATTENING (stronger noise filtering)
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

    # Optional integrations
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
                title = str(c.get('title', ''))
                body = str(c.get('body', ''))
                if title or body:
                    pairs.append((f"dynamic.cards[{i}].title", title))
                    pairs.append((f"dynamic.cards[{i}].body", body))
        if isinstance(kv, list):
            for p in kv:
                k = str(p.get("key", ""))
                v = str(p.get("value", ""))
                if k:
                    pairs.append((f"dynamic.kv.{k}", v))

    # Dedupe
    seen = set()
    deduped: List[Tuple[str, str]] = []
    for k, v in pairs:
        if k not in seen:
            seen.add(k)
            deduped.append((k, v))

    # Stronger noise filter
    filtered = []
    noisy = [
        "<!doctype", "<html", "script", "base64,", "data:image/", "function(", "{", "}", "[object",
        "charset=", " style=", " class=", "<svg", "</svg"
    ]
    for k, v in deduped:
        v_low = str(v).lower()
        if any(s in v_low for s in noisy):
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
        # Phase 1: bigger, crisper, darker
        self.styles.add(ParagraphStyle('Muted', fontSize=9, textColor=MUTED_GREY, leading=12, fontName=base_font))
        self.styles.add(ParagraphStyle('H2', parent=self.styles['Heading2'], textColor=PRIMARY_DARK, fontName=base_font))
        self.styles.add(ParagraphStyle('H3', parent=self.styles['Heading3'], textColor=PRIMARY_DARK, fontName=base_font))
        self.styles.add(ParagraphStyle('Note', fontSize=9, textColor=MUTED_GREY, leading=12, fontName=base_font))
        self.styles.add(ParagraphStyle('Tiny', fontSize=8, textColor=MUTED_GREY, fontName=base_font))
        self.styles.add(ParagraphStyle('Brand', fontSize=36, textColor=PRIMARY_DARK, fontName=base_font))
        self.styles.add(ParagraphStyle('ReportTitle', fontSize=28, leading=32, textColor=PRIMARY_DARK, fontName=base_font))
        self.styles.add(ParagraphStyle('Caption', fontSize=8, textColor=MUTED_GREY, leading=10, fontName=base_font))
        self.styles.add(ParagraphStyle('KPI', fontSize=11, textColor=PRIMARY_DARK, leading=13, fontName=base_font))

        # Integrity & IDs
        self.integrity = _hash_integrity(audit)
        self.report_id = _short_id_from_hash(self.integrity)

        # Header fields
        self.brand = audit.get("brand_name", PDF_BRAND_NAME) or PDF_BRAND_NAME
        self.client = audit.get("client_name", None)
        self.url = audit.get("audited_url", None)
        self.site_name = audit.get("website_name", None) or self.url
        self.audit_dt = audit.get("audit_datetime", _now_str())

        # Scores
        self.scores = dict(audit.get("scores", {}))
        # Maintain backward compatibility; do not display missing values
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
        host = _hostname(self.url or "")
        perf_extras = _safe_get(self.data, ["breakdown", "performance", "extras"], {})
        self.overview = {
            "domain": host or None,
            "ip": _get_ip(host) if host else None,
            "hosting_provider": None,
            "server_location": None,
            "cms": None,
            "ssl_status": "HTTPS" if _safe_get(self.data, ["breakdown", "security"]).get("https", False) else ("HTTP" if _safe_get(self.data, ["breakdown", "security"]).get("https") is not None else None),
            "http_to_https": None,
            "load_ms": _int_or(perf_extras.get("load_ms", 0), 0) or None,
            "page_size": _kb(_int_or(perf_extras.get("bytes", 0), 0)),
            "total_requests_approx": int(
                _int_or(perf_extras.get("scripts", 0), 0)
                + _int_or(perf_extras.get("styles", 0), 0)
                + 1
            ) or None,
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

    # --------------------- utilities (Phase 2) ---------------------
    def _filter_rows(self, rows: List[List[Any]]) -> List[List[Any]]:
        """Keep only data rows (index>=1) whose value is present (not None/empty)."""
        if not rows:
            return rows
        header = rows[0]
        out = [header]
        for r in rows[1:]:
            if len(r) < 2:
                continue
            val = r[1]
            present = (val is not None) and (str(val).strip() != "")
            if present:
                out.append(r)
        return out

    def _render_clean_table(self, rows: List[List[Any]], colWidths: List[float], header_bg, fontsize=9):
        """Render only if there is at least one data row kept; otherwise print a muted note."""
        filtered = self._filter_rows(rows)
        if len(filtered) <= 1:
            return Paragraph("No data detected. Fields shown only when data is available from the runner.", self.styles['Muted'])
        return _zebra_table(filtered, colWidths=colWidths, header_bg=header_bg, fontsize=fontsize)

    def _section_data_note(self, elems: List[Any]):
        elems.append(Spacer(1, 0.06 * inch))
        elems.append(Paragraph("Fields shown only when data is available from the runner.", self.styles['Muted']))

    # --------------------- page decorators ---------------------
    def _watermark(self, canvas: Canvas):
        # Phase 1: softer watermark for cover/readability
        try:
            canvas.saveState()
            canvas.setFillColor(colors.Color(0.1, 0.1, 0.2, alpha=0.025))  # reduced opacity
            canvas.setFont('Helvetica', 48)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, f"{self.brand} • Confidential")
        finally:
            canvas.restoreState()

    def _footer(self, canvas: Canvas, doc):
        self._watermark(canvas)
        canvas.saveState()
        canvas.setFillColor(ACCENT_INDIGO)
        canvas.rect(0, 0.45 * inch, A4[0], 0.02 * inch, fill=1, stroke=0)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(PRIMARY_DARK)
        canvas.drawString(inch, 0.28 * inch, f"{self.brand} | Integrity: {self.integrity[:16]}…")
        canvas.drawRightString(A4[0] - inch, 0.28 * inch, f"Page {doc.page}")
        if doc.page == 1:
            try:
                canvas.setTitle(f"{self.site_name or 'Website'} – Website Audit Report")
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
        block.append(Spacer(1, 0.55 * inch))

        if isinstance(PDF_LOGO_PATH, str) and PDF_LOGO_PATH and os.path.exists(PDF_LOGO_PATH):
            try:
                block.append(Image(PDF_LOGO_PATH, width=1.8 * inch, height=1.8 * inch))
                block.append(Spacer(1, 0.25 * inch))
            except Exception:
                pass
        else:
            block.append(_chip(self.brand, ACCENT_INDIGO, pad_x=10, pad_y=4, font_size=11))
            block.append(Spacer(1, 0.18 * inch))

        # Phase 1: Larger, crisp, high-contrast titles
        block.append(Paragraph(self.brand.upper(), self.styles['Brand']))
        block.append(Paragraph("Website Performance & Compliance Dossier", self.styles['ReportTitle']))
        block.append(Spacer(1, 0.28 * inch))

        # KPI chips (bigger/higher contrast)
        block.append(
            Table([
                [
                    _chip(
                        f"Risk: {self.risk}",
                        {'Low': SUCCESS_GREEN, 'Medium': WARNING_ORANGE, 'High': colors.HexColor('#E67E22'), 'Critical': CRITICAL_RED}[self.risk],
                        pad_x=10, pad_y=5, font_size=11
                    )
                ],
                [
                    _chip(f"Overall: {self.overall}/100", ACCENT_BLUE, pad_x=10, pad_y=5, font_size=11)
                ]
            ], colWidths=[2.2 * inch], hAlign='LEFT', style=[('VALIGN', (0, 0), (-1, -1), 'MIDDLE')])
        )
        block.append(Spacer(1, 0.22 * inch))

        # Divider + details table
        block.append(HRFlowable(width="100%", thickness=0.6, color=DIVIDER_GRAY))
        block.append(Spacer(1, 0.10 * inch))

        rows = [["Field", "Value"]]
        if self.url:
            rows.append(["Website URL Audited", self.url])
        if self.audit_dt:
            rows.append(["Audit Date & Time", self.audit_dt])
        rows.append(["Report ID", self.report_id])
        rows.append(["Generated By", SAAS_NAME])

        block.append(self._render_clean_table(rows, colWidths=[2.6 * inch, 3.7 * inch], header_bg=PALE_BLUE, fontsize=10))
        block.append(Spacer(1, 0.16 * inch))
        block.append(Paragraph(
            "This report contains confidential and proprietary information intended solely for the recipient. "
            "Unauthorized distribution is prohibited.", self.styles['Muted']))

        elems.append(KeepTogether(block))
        elems.append(PageBreak())

    def toc_page(self, elems: List[Any]):
        elems.append(self._section_title("Contents"))
        bullets_list = [
            "Executive Summary",
            "Executive Highlights",
            "Core Web Vitals (Field/Lab)",
            "What We Audited (Homepage Snapshot)",
            "Website Overview",
            "SEO Audit",
            "Performance Audit",
            "Security Audit",
            "Accessibility Audit",
            "User Experience (UX) & Mobile",
            "Industry Benchmark Comparison",
            "Business & Revenue Impact (Modeled)",
            "Competitive Analysis (if available)",
            "Crawl Summary (if available)",
            "Visual Proof of Issues (if available)",
            "Broken Link Analysis",
            "Analytics & Tracking",
            "Critical Issues Summary",
            "Recommendations & Fix Roadmap",
            "30-60-90 Day Plan",
            "Scoring Methodology",
            "Website Maturity Index",
            "Risk Matrix",
            "Appendix (Technical Details)",
        ]
        for b in bullets_list:
            elems.append(Paragraph(f"• {escape(b)}", self.styles['Normal']))
        elems.append(Spacer(1, 0.10 * inch))
        elems.append(Paragraph("Note: Page numbers are included in the footer.", self.styles['Muted']))
        elems.append(PageBreak())

    def _score_discrepancy_note(self) -> Optional[Paragraph]:
        try:
            delta = abs(int(self.runner_overall) - int(self.overall))
            if delta >= 10:
                return Paragraph(
                    f"<b>Score Consistency:</b> Runner {self.runner_overall}/100 vs computed {self.overall}/100. "
                    f"Computed score is used for all charts for consistency (weights applied).",
                    self.styles['Note']
                )
        except Exception:
            pass
        return None

    def executive_summary(self, elems: List[Any]):
        elems.append(self._section_title("Executive Health Summary"))

        radar = Image(_radar_chart(self.scores), width=2.8 * inch, height=2.8 * inch)
        bars = Image(_bar_chart(self.scores), width=3.0 * inch, height=2.2 * inch)
        donut = Image(_donut_overall(self.overall), width=2.0 * inch, height=2.0 * inch)
        grid = Table([[radar, Table([[bars], [donut]], style=[('ALIGN', (0, 0), (-1, -1), 'CENTER')])]],
                     colWidths=[3.0 * inch, 3.1 * inch])
        grid.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        elems.append(grid)
        elems.append(Paragraph(
            "Chart captions: Radar shows category distribution; Bar shows category scores; Donut shows computed overall (weighted).",
            self.styles['Caption']
        ))
        elems.append(Spacer(1, 0.12 * inch))

        krows = [["Field", "Value"]]
        krows.append(["Overall Website Health (computed)", f"{self.overall}/100"])
        if self.runner_overall != self.overall:
            krows.append(["Overall (runner provided)", f"{self.runner_overall}/100"])
        krows.append(["Overall Risk Level", self.risk])
        if "seo" in self.scores:
            krows.append(["SEO Score", str(int(self.scores.get("seo", 0)))])
        if "performance" in self.scores:
            krows.append(["Performance Score", str(int(self.scores.get("performance", 0)))])
        if "security" in self.scores:
            krows.append(["Security Score", str(int(self.scores.get("security", 0)))])
        if "accessibility" in self.scores:
            krows.append(["Accessibility Score", str(int(self.scores.get("accessibility", 0)))])
        if "ux" in self.scores:
            krows.append(["UX Score", str(int(self.scores.get("ux", 0)))])
        if "links" in self.scores:
            krows.append(["Links Score", str(int(self.scores.get("links", 0)))])
        elems.append(self._render_clean_table(krows, colWidths=[2.9 * inch, 3.4 * inch], header_bg=PALE_GREEN, fontsize=10))
        elems.append(Spacer(1, 0.05 * inch))

        discrepancy = self._score_discrepancy_note()
        if discrepancy:
            elems.append(discrepancy)

        elems.append(Spacer(1, 0.10 * inch))
        # Strategic executive takeaways (non-numeric if data missing)
        elems.append(Paragraph(
            "<b>Executive View:</b> Address the top issues to reduce business risk, protect brand trust, and improve conversions. ",
            self.styles['Note']
        ))

        elems.append(Spacer(1, 0.12 * inch))
        elems.append(Paragraph("Top Critical Issues & Estimated Business Impact", self.styles['H2']))
        issues = self.issues[:5]
        if not issues:
            elems.append(Paragraph("No critical issues derived from available data.", self.styles['Muted']))
        else:
            rows = [["Priority", "Issue", "Category", "Impact", "Recommended Fix"]]
            for i in issues:
                rows.append([i["priority"], i["issue"], i["category"], i["impact"], i["fix"]])
            t = self._table(rows, colWidths=[0.95 * inch, 2.25 * inch, 0.9 * inch, 1.5 * inch, 1.6 * inch], header_bg=ACCENT_BLUE, fontsize=8)
            for r in range(1, len(rows)):
                pr = rows[r][0]
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, r), (0, r), {'🔴 Critical': CRITICAL_RED, '🟠 High': WARNING_ORANGE, '🟡 Medium': YELLOW}.get(pr, SUCCESS_GREEN)),
                    ('TEXTCOLOR', (0, r), (0, r), colors.whitesmoke)
                ]))
            elems.append(t)
        self._section_data_note(elems)
        elems.append(PageBreak())

    def executive_one_pager(self, elems: List[Any]):
        elems.append(self._section_title("Executive Highlights"))
        donut_overall = Image(_donut_overall(self.overall), width=2.0 * inch, height=2.0 * inch)
        cats = ["performance", "seo", "security", "accessibility"]
        smalls = []
        for c in cats:
            if c in self.scores:
                val = int(self.scores.get(c, 0))
                img = Image(_donut_overall(val, title=c.upper()), width=1.5 * inch, height=1.5 * inch)
                smalls.append(Table([[Paragraph(c.upper(), self.styles['Tiny'])], [img]],
                                    style=[('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
        grid = Table([[donut_overall, Table([smalls[:2], smalls[2:]], style=[('ALIGN', (0, 0), (-1, -1), 'CENTER')])]],
                     colWidths=[2.5 * inch, 3.6 * inch])
        grid.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        elems.append(grid)
        elems.append(Paragraph("Gauges summarize overall and category health at a glance.", self.styles['Caption']))
        elems.append(Spacer(1, 0.08 * inch))

        # Trend arrows (if history present)
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
                    rows.append([str(h.get("dt", "")), str(h.get("overall", "")), "", str(h.get("performance", "")), ""])
                rows.append(["Latest change", str(b.get("overall", "")), overall_arrow, str(b.get("performance", "")), perf_arrow])
                elems.append(Paragraph("Recent Trend (Overall / Performance)", self.styles['H2']))
                elems.append(self._table(rows, colWidths=[1.5 * inch, 1.2 * inch, 0.4 * inch, 1.4 * inch, 0.4 * inch], header_bg=PALE_GREEN))
            except Exception:
                pass
        self._section_data_note(elems)
        elems.append(PageBreak())

    # --------------------- NEW: Core Web Vitals Section ---------------------
    def core_web_vitals_section(self, elems: List[Any]):
        elems.append(self._section_title("Core Web Vitals (Field/Lab)"))
        lh_metrics = self.lh.get('metrics', {}) if isinstance(self.lh, dict) else {}
        field = self.data.get('field_cwv', {}) if isinstance(self.data.get('field_cwv', {}), dict) else {}
        mobile_lab = self.mobile.get('lab_metrics', {}) if isinstance(self.mobile.get('lab_metrics', {}), dict) else {}

        # Build comparative table
        rows = [["Metric", "Desktop", "Mobile", "Benchmark", "Status"]]

        def status_for(metric_key: str, val: Optional[float]) -> str:
            if val is None:
                return "Data Not Collected"
            # Simple thresholds; can be refined
            if metric_key == 'CLS':
                try:
                    v = float(val)
                    if v <= 0.1:
                        return "Good"
                    elif v <= 0.25:
                        return "Needs Improvement"
                    return "Poor"
                except Exception:
                    return "Data Not Collected"
            else:
                # ms-based metrics
                try:
                    v = float(val)
                    if metric_key in ('LCP_ms', 'FCP_ms', 'INP_ms', 'TTFB_ms', 'SpeedIndex_ms'):
                        if metric_key == 'INP_ms':
                            if v <= 200:
                                return "Good"
                            elif v <= 500:
                                return "Needs Improvement"
                            return "Poor"
                        if metric_key == 'LCP_ms':
                            if v <= 2500:
                                return "Good"
                            elif v <= 4000:
                                return "Needs Improvement"
                            return "Poor"
                        if metric_key == 'TTFB_ms':
                            if v <= 800:
                                return "Good"
                            elif v <= 1800:
                                return "Needs Improvement"
                            return "Poor"
                        # Fallback for others
                        return "OK"
                except Exception:
                    return "Data Not Collected"
            return "OK"

        def fmt_ms_or_blank(v: Any) -> Optional[str]:
            s = _ms(v)
            return s if s else None

        metrics_order = [
            ("Largest Contentful Paint", 'LCP_ms'),
            ("Interaction to Next Paint", 'INP_ms'),
            ("Cumulative Layout Shift", 'CLS'),
            ("Time to First Byte", 'TTFB_ms'),
            ("First Contentful Paint", 'FCP_ms')
        ]

        any_row = False
        for label, key in metrics_order:
            desktop_val = lh_metrics.get(key) if lh_metrics else None
            mobile_val = mobile_lab.get(key) if mobile_lab else None
            bench = self.bench.get('avg', {}).get(key) if isinstance(self.bench.get('avg', {}), dict) else None

            # Prefer field data if present
            if key in ('LCP_ms', 'INP_ms', 'TTFB_ms'):
                desktop_field = field.get('desktop', {}).get(key) if isinstance(field.get('desktop', {}), dict) else None
                mobile_field = field.get('mobile', {}).get(key) if isinstance(field.get('mobile', {}), dict) else None
                if desktop_field is not None:
                    desktop_val = desktop_field
                if mobile_field is not None:
                    mobile_val = mobile_field

            d = fmt_ms_or_blank(desktop_val) if key != 'CLS' else (str(desktop_val) if desktop_val is not None else None)
            m = fmt_ms_or_blank(mobile_val) if key != 'CLS' else (str(mobile_val) if mobile_val is not None else None)
            b = fmt_ms_or_blank(bench) if key != 'CLS' else (str(bench) if bench is not None else None)
            st = status_for(key, mobile_val if mobile_val is not None else desktop_val)

            # Only add if any value present; otherwise leave table but show note later
            if any([d, m, b]):
                any_row = True
                rows.append([label, d or "—", m or "—", b or "—", st])

        if any_row:
            elems.append(self._table(rows, colWidths=[2.1 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.4 * inch], header_bg=PALE_BLUE, fontsize=9))
            elems.append(Paragraph("If a column shows ‘—’, it means that value wasn’t provided by the runner.", self.styles['Caption']))
        else:
            elems.append(Paragraph("Data Not Collected: No Core Web Vitals provided by runner.", self.styles['Muted']))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def what_we_audited(self, elems: List[Any]):
        elems.append(self._section_title("What We Audited (Homepage Snapshot)"))
        ctx_rows = [["Field", "Value"]]
        final_url = str(self.lh.get("final_url", self.url)) if isinstance(self.lh, dict) else (self.url or "")
        if final_url:
            ctx_rows.append(["Final URL", final_url])
        cfg = self.lh.get("config", {}) if isinstance(self.lh, dict) else {}
        if cfg:
            device = cfg.get("device"); form = cfg.get("form_factor")
            label_val = " / ".join([x for x in [device, form] if x])
            if label_val:
                ctx_rows.append(["Device / Form Factor", label_val])
        elems.append(self._render_clean_table(ctx_rows, colWidths=[2.6 * inch, 3.7 * inch], header_bg=LIGHT_GRAY_BG))
        elems.append(Spacer(1, 0.10 * inch))

        cats = self.lh.get("categories", {}) if isinstance(self.lh, dict) else {}
        perf_val = cats.get("performance", None)
        if perf_val is not None:
            perf_chip_bg = _perf_color(perf_val)
            elems.append(_chip(f"Lighthouse Performance: {_pct(perf_val)}/100", perf_chip_bg, pad_x=10, pad_y=5, font_size=11))
            elems.append(Spacer(1, 0.12 * inch))

        img_buf = _load_homepage_screenshot(self.assets)
        if img_buf:
            try:
                elems.append(Image(img_buf, width=5.8 * inch, height=3.35 * inch))
            except Exception:
                elems.append(Paragraph("Screenshot could not be rendered.", self.styles['Muted']))
        else:
            elems.append(Paragraph("Screenshot not available.", self.styles['Muted']))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def website_overview(self, elems: List[Any]):
        elems.append(self._section_title("Website Overview"))
        rows = [["Field", "Value"]]
        for label, val in [
            ("Domain Name", self.overview.get("domain")),
            ("IP Address", self.overview.get("ip")),
            ("SSL Status", self.overview.get("ssl_status")),
            ("Page Load Time", f"{self.overview.get('load_ms')} ms" if self.overview.get('load_ms') else None),
            ("Page Size", self.overview.get("page_size")),
            ("Total Requests (approx)", str(self.overview.get("total_requests_approx")) if self.overview.get("total_requests_approx") else None),
        ]:
            if val:
                rows.append([label, val])

        # Benchmarks & competitors (optional line-level context)
        if isinstance(self.bench, dict) and self.bench.get("avg"):
            avg = self.bench["avg"]
            bench_line = []
            if avg.get("LCP_ms") is not None:
                bench_line.append(f"LCP {_ms(avg.get('LCP_ms'))}")
            if avg.get("INP_ms") is not None:
                bench_line.append(f"INP {_ms(avg.get('INP_ms', avg.get('INP')))}")
            if avg.get("CLS") is not None:
                bench_line.append(f"CLS {avg.get('CLS')}")
            if avg.get("Performance") is not None:
                bench_line.append(f"Perf {avg.get('Performance')}")
            if bench_line:
                rows.append(["Benchmark (context)", " | ".join([x for x in bench_line if x])])

        if isinstance(self.competitors, dict) and self.competitors.get("summary"):
            comp = str(self.competitors["summary"])
            rows.append(["Competitor Comparison", comp[:220] + ("…" if len(comp) > 220 else "")])

        elems.append(self._render_clean_table(rows, colWidths=[2.7 * inch, 3.6 * inch], header_bg=PALE_BLUE))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def seo_section(self, elems: List[Any]):
        elems.append(self._section_title("SEO Audit"))
        seo = _safe_get(self.data, ["breakdown", "seo"], {})
        ex = seo.get("extras", {}) if isinstance(seo, dict) else {}

        # On-page
        on_rows = [["Field", "Value"]]
        title = ex.get("title") or None
        if title:
            on_rows.append(["Title tag (length + optimization)", f"{len(title)} chars"])
        if isinstance(ex.get("meta_description_present"), bool):
            on_rows.append(["Meta description (length + optimization)", "Present" if ex.get("meta_description_present") else "Missing"])
        h1_count = _int_or(ex.get("h1_count", 0), 0)
        if h1_count:
            on_rows.append(["H1, H2 structure", f"H1 count: {h1_count}; H2: (runner not supplied)"])
        canonical = ex.get("canonical")
        if canonical:
            on_rows.append(["Canonical tag presence", "Yes"])
        imgs_total = _int_or(ex.get("images_total", 0), 0) or None
        imgs_missing = _int_or(ex.get("images_missing_alt", 0), 0) or None
        if imgs_total is not None:
            on_rows.append(["Image ALT attributes missing", f"{imgs_missing or 0}/{imgs_total}"])
        elems.append(self._render_clean_table(on_rows, colWidths=[3.1 * inch, 3.2 * inch], header_bg=PALE_YELLOW))
        elems.append(Spacer(1, 0.08 * inch))

        # Technical
        tech_rows = [["Field", "Value"]]
        if isinstance(self.robots.get("exists"), bool):
            tech_rows.append(["Robots.txt", "Present" if self.robots.get("exists") else "Not Detected"])
        if "allows_all" in self.robots:
            tech_rows.append(["Robots rules", f"Allows all: {bool(self.robots.get('allows_all'))}"])
        if isinstance(self.sitemap.get("exists"), bool):
            label = "Present & Valid" if self.sitemap.get("exists") and self.sitemap.get("valid") else ("Present" if self.sitemap.get("exists") else "Not Detected")
            tech_rows.append(["Sitemap.xml", label])
        if self.sitemap.get("url_count"):
            tech_rows.append(["Sitemap URLs (approx)", str(self.sitemap.get("url_count"))])
        if isinstance(self.schema.get("detected"), bool):
            tech_rows.append(["Structured data detected", "Yes" if self.schema.get("detected") else "Not Detected"])
        if self.schema.get("items"):
            tech_rows.append(["Schema types", ", ".join(self.schema.get("items", [])[:8])])
        if self.schema.get("errors") or self.schema.get("warnings"):
            errs = f"Errors: {len(self.schema.get('errors', []))}" if self.schema.get("errors") else ""
            warns = f"Warnings: {len(self.schema.get('warnings', []))}" if self.schema.get("warnings") else ""
            tech_rows.append(["Schema issues", " | ".join([x for x in [errs, warns] if x])])
        # CWV (lab)
        metrics = self.lh.get('metrics', {}) if isinstance(self.lh, dict) else {}
        cwv_line = []
        if metrics.get("LCP_ms") is not None:
            cwv_line.append(f"LCP {_ms(metrics.get('LCP_ms'))}")
        if metrics.get("INP_ms") is not None:
            cwv_line.append(f"INP {_ms(metrics.get('INP_ms'))}")
        if metrics.get("CLS") is not None:
            cwv_line.append(f"CLS {metrics.get('CLS')}")
        if cwv_line:
            tech_rows.append(["Core Web Vitals (lab)", " | ".join([x for x in cwv_line if x])])
        # Mobile viewport
        if isinstance(self.mobile.get("viewport_meta"), bool):
            tech_rows.append(["Mobile responsiveness", "Viewport OK" if self.mobile.get("viewport_meta") else "Viewport missing"])
        elems.append(self._render_clean_table(tech_rows, colWidths=[3.1 * inch, 3.2 * inch], header_bg=PALE_BLUE))
        self._section_data_note(elems)
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
        if perf_val is not None:
            perf_chip_bg = _perf_color(perf_val)
            elems.append(_chip(f"Lighthouse Performance: {_pct(perf_val)}/100", perf_chip_bg, pad_x=10, pad_y=5, font_size=11))
            elems.append(Spacer(1, 0.10 * inch))

        top_rows = [["Metric", "Value"]]
        label = " / ".join([x for x in [cfg.get('device'), cfg.get('form_factor')] if x])
        if label:
            top_rows.append(["Device / Form Factor", label])
        if m.get("LCP_ms") is not None:
            top_rows.append(["Largest Contentful Paint (LCP)", _ms(m.get("LCP_ms"))])
        if m.get("INP_ms") is not None:
            top_rows.append(["Interaction to Next Paint (INP)", _ms(m.get("INP_ms"))])
        if m.get("CLS") is not None:
            top_rows.append(["Cumulative Layout Shift (CLS)", str(m.get("CLS"))])
        if m.get("FCP_ms") is not None:
            top_rows.append(["First Contentful Paint (FCP)", _ms(m.get("FCP_ms"))])
        if m.get("TTFB_ms") is not None:
            top_rows.append(["Time to First Byte (TTFB)", _ms(m.get("TTFB_ms"))])
        if m.get("SpeedIndex_ms") is not None:
            top_rows.append(["Speed Index", _ms(m.get("SpeedIndex_ms"))])
        if m.get("TBT_ms") is not None:
            top_rows.append(["Total Blocking Time (TBT)", _ms(m.get("TBT_ms"))])
        elems.append(self._render_clean_table(top_rows, colWidths=[3.6 * inch, 2.7 * inch], header_bg=PALE_GREEN))
        elems.append(Paragraph(
            "Interpretation: LCP < 2.5s (good), INP < 200ms (good), CLS < 0.1 (good). Values shown are lab metrics when provided.",
            self.styles['Caption']
        ))
        elems.append(Spacer(1, 0.08 * inch))

        # Opportunities
        elems.append(Paragraph("Opportunities (estimated savings)", self.styles['H2']))
        if opps:
            rows = [["Opportunity", "Est. Savings"]]
            for o in opps[:8]:
                title = str(o.get("title", "")).strip()
                savings = _ms(o.get("estimated_savings_ms"))
                if title and savings:
                    rows.append([title, savings])
            if len(rows) > 1:
                elems.append(self._table(rows, colWidths=[4.2 * inch, 2.1 * inch], header_bg=PALE_BLUE))
            else:
                elems.append(Paragraph("No opportunities detected.", self.styles['Muted']))
        else:
            elems.append(Paragraph("No opportunities detected.", self.styles['Muted']))
        elems.append(Spacer(1, 0.06 * inch))

        # Diagnostics
        elems.append(Paragraph("Diagnostics", self.styles['H2']))
        if diags:
            rows = [["Check", "Value/Note"]]
            for d in diags[:10]:
                dv = str(d.get("id","")).strip()
                val = str(d.get("value","")).strip()
                if dv and val:
                    rows.append([dv, val])
            if len(rows) > 1:
                elems.append(self._table(rows, colWidths=[2.4 * inch, 3.9 * inch], header_bg=PALE_YELLOW))
            else:
                elems.append(Paragraph("No diagnostics detected.", self.styles['Muted']))
        else:
            elems.append(Paragraph("No diagnostics detected.", self.styles['Muted']))

        self._section_data_note(elems)
        elems.append(PageBreak())

    def security_section(self, elems: List[Any]):
        elems.append(self._section_title("Security Audit"))
        sec = _safe_get(self.data, ["breakdown", "security"], {})
        deep = self.secdeep if isinstance(self.secdeep, dict) else {}
        hdrs = deep.get("headers", {}) if isinstance(deep.get("headers", {}), dict) else {}
        csp_info = _analyze_csp(hdrs.get("content-security-policy", "")) if hdrs else {"present": False}
        cookies = deep.get("cookies", []) if isinstance(deep.get("cookies", []), list) else []

        insecure = sum(1 for c in cookies if not c.get("secure"))
        no_http_only = sum(1 for c in cookies if not c.get("httpOnly"))
        unknown_same_site = sum(1 for c in cookies if str(c.get("sameSite","Unknown")) == "Unknown")

        rows = [["Check", "Status/Details"]]
        if isinstance(sec.get("https"), bool):
            rows.append(["HTTPS Enabled", "Yes" if sec.get("https") else "No"])
        if sec.get("status_code") is not None:
            rows.append(["Origin Status Code", str(sec.get("status_code"))])
        if isinstance(sec.get("hsts"), bool):
            rows.append(["HSTS Enabled", "Yes" if sec.get("hsts") else "No"])
        if hdrs.get("content-security-policy") or csp_info.get("present"):
            risk_bits = []
            if csp_info.get("unsafe_inline"): risk_bits.append("unsafe-inline")
            if csp_info.get("unsafe_eval"): risk_bits.append("unsafe-eval")
            rows.append(["Content-Security-Policy", "Present" + (f" (risks: {', '.join(risk_bits)})" if risk_bits else "")])
        if deep.get("mixed_content") is not None:
            rows.append(["Mixed content issues", str(deep.get("mixed_content"))])
        if isinstance(deep.get("security_txt",{}).get("exists"), bool):
            rows.append(["security.txt", "Present" if deep.get("security_txt",{}).get("exists") else "Not Detected"])
        if cookies:
            rows.append(["Cookies (sample)", f"{len(cookies)} found; insecure={insecure}, no HttpOnly={no_http_only}, SameSite unknown={unknown_same_site}"])
        if hdrs.get("x-frame-options"):
            rows.append(["X-Frame-Options", hdrs.get("x-frame-options")])
        if hdrs.get("x-content-type-options"):
            rows.append(["X-Content-Type-Options", hdrs.get("x-content-type-options")])

        elems.append(self._render_clean_table(rows, colWidths=[3.2 * inch, 3.1 * inch], header_bg=PALE_RED))

        # Security Maturity (basic heuristic)
        maturity = 1
        if sec.get('https') and sec.get('hsts') and hdrs.get('content-security-policy'):
            maturity = 2
        if maturity == 2 and hdrs.get('x-frame-options') and hdrs.get('x-content-type-options'):
            maturity = 3
        elems.append(Spacer(1, 0.06 * inch))
        elems.append(Paragraph(f"Security Maturity Level: <b>Level {maturity}</b> (1=Basic, 2=Hardened, 3=Enterprise)", self.styles['Note']))

        self._section_data_note(elems)
        elems.append(PageBreak())

    def accessibility_section(self, elems: List[Any]):
        elems.append(self._section_title("Accessibility Audit"))
        ex = _safe_get(self.data, ["breakdown", "seo", "extras"], {})
        axe = self.a11y.get("axe", {}) if isinstance(self.a11y, dict) else {}
        counts = axe.get("counts", {})
        lvls = axe.get("by_wcag_level", {})
        buckets = axe.get("buckets", {})
        top_issues = axe.get("top_issues", []) or []

        rows1 = [["Check", "Result"]]
        imgs_total = _int_or(ex.get("images_total", 0), 0) or None
        imgs_missing = _int_or(ex.get("images_missing_alt", 0), 0) or None
        if imgs_total is not None:
            rows1.append(["Missing ALT tags", f"{imgs_missing or 0}/{imgs_total}"])
        if counts.get("violations") is not None:
            rows1.append(["Violations (axe)", str(counts.get("violations"))])
        if lvls:
            rows1.append(["WCAG Levels (A/AA/AAA)", f"{lvls.get('A','0')}/{lvls.get('AA','0')}/{lvls.get('AAA','0')}"])
        if buckets.get("color-contrast") is not None:
            rows1.append(["Contrast issues", str(buckets.get("color-contrast"))])
        if buckets.get("aria") is not None:
            rows1.append(["ARIA issues", str(buckets.get("aria"))])
        if buckets.get("keyboard") is not None:
            rows1.append(["Keyboard issues", str(buckets.get("keyboard"))])
        if buckets.get("landmarks") is not None:
            rows1.append(["Landmarks issues", str(buckets.get("landmarks"))])
        if buckets.get("forms") is not None:
            rows1.append(["Forms/Labels issues", str(buckets.get("forms"))])

        elems.append(self._render_clean_table(rows1, colWidths=[3.2 * inch, 3.1 * inch], header_bg=PALE_YELLOW))
        elems.append(Paragraph("WCAG target: 2.2 AA (contrast ≥ 4.5:1, keyboard operability, meaningful order).", self.styles['Caption']))
        elems.append(Spacer(1, 0.06 * inch))

        if top_issues:
            rows2 = [["Rule", "Nodes", "Selectors / Examples"]]
            for t in top_issues[:8]:
                rule = str(t.get("id","")).strip()
                nodes = str(t.get("nodes","")).strip()
                examples = ", ".join((t.get("examples", [])[:3]))
                if rule and nodes:
                    rows2.append([rule, nodes, examples])
            if len(rows2) > 1:
                elems.append(self._table(rows2, colWidths=[1.8 * inch, 0.8 * inch, 3.7 * inch], header_bg=PALE_BLUE, fontsize=8))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def ux_section(self, elems: List[Any]):
        elems.append(self._section_title("User Experience (UX) & Mobile"))
        rows = [["Check", "Result"]]
        if isinstance(self.mobile.get("viewport_meta"), bool):
            rows.append(["Mobile friendliness", "Viewport OK" if self.mobile.get("viewport_meta") else "Viewport missing"])
        if self.mobile.get("tap_targets_small") is not None:
            rows.append(["Tap targets too small", str(self.mobile.get("tap_targets_small"))])
        if self.mobile.get("font_size_issues") is not None:
            rows.append(["Problematic font sizes", str(self.mobile.get("font_size_issues"))])
        if self.mobile.get("layout_shift_risk") is not None:
            rows.append(["Layout shift risk (mobile)", str(self.mobile.get("layout_shift_risk"))])

        elems.append(self._render_clean_table(rows, colWidths=[3.2 * inch, 3.1 * inch], header_bg=PALE_BLUE))
        # Simple grade
        try:
            perf = int(self.scores.get('performance', 0))
            a11y = int(self.scores.get('accessibility', 0))
            grade = 'A' if perf >= 85 and a11y >= 85 else ('B' if perf >= 70 else ('C' if perf >= 50 else 'D'))
            elems.append(Spacer(1, 0.06 * inch))
            elems.append(Paragraph(f"Mobile Usability Grade: <b>{grade}</b>", self.styles['Note']))
        except Exception:
            pass
        self._section_data_note(elems)
        elems.append(PageBreak())

    # --------------------- NEW: Industry Benchmark ---------------------
    def industry_benchmark_section(self, elems: List[Any]):
        elems.append(self._section_title("Industry Benchmark Comparison"))
        avg = self.bench.get('avg') if isinstance(self.bench, dict) else None
        if not isinstance(avg, dict) or not avg:
            elems.append(Paragraph("Data Not Collected: No benchmark block provided by runner.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return
        rows = [["Category", "Your Score", "Industry Avg", "Top 10%", "Position"]]
        def pos(your, industry):
            try:
                y = float(your); i = float(industry)
                return "Above Avg" if y > i else ("At Avg" if abs(y - i) <= 1 else "Below Avg")
            except Exception:
                return "—"
        cats = [
            ("Performance", self.scores.get('performance'), avg.get('Performance'), avg.get('Top10_Performance')),
            ("SEO", self.scores.get('seo'), avg.get('SEO'), avg.get('Top10_SEO')),
            ("Security", self.scores.get('security'), avg.get('Security'), avg.get('Top10_Security')),
            ("Accessibility", self.scores.get('accessibility'), avg.get('Accessibility'), avg.get('Top10_Accessibility'))
        ]
        added = False
        for name, your, industry, top in cats:
            if your is None and industry is None:
                continue
            added = True
            rows.append([name, str(your) if your is not None else "—", str(industry) if industry is not None else "—", str(top) if top is not None else "—", pos(your, industry)])
        if added:
            elems.append(self._table(rows, colWidths=[1.8 * inch, 1.0 * inch, 1.2 * inch, 1.0 * inch, 1.2 * inch], header_bg=PALE_GREEN))
        else:
            elems.append(Paragraph("No comparable categories were provided.", self.styles['Muted']))
        self._section_data_note(elems)
        elems.append(PageBreak())

    # --------------------- NEW: Business Impact ---------------------
    def business_impact_section(self, elems: List[Any]):
        elems.append(self._section_title("Business & Revenue Impact (Modeled)"))
        elems.append(Paragraph(
            "This section provides a modeled, non-binding estimate of potential business impact based on common industry studies. "
            "Replace with analytics data when available.", self.styles['Note']))
        perf = _int_or(self.scores.get('performance', 0), 0)
        a11y = _int_or(self.scores.get('accessibility', 0), 0)
        risk = self.risk
        bullets = []
        if perf < 70:
            bullets.append("Improving load speed can materially increase conversion rates and reduce bounce on mobile.")
        if a11y < 70:
            bullets.append("Accessibility gaps can limit reach and increase compliance exposure (WCAG 2.2 AA).")
        if risk in ("High", "Critical"):
            bullets.append("Current risk posture may affect brand trust and revenue stability.")
        if not bullets:
            bullets.append("No immediate business risks inferred from available data; continue monitoring and incremental optimization.")
        for b in bullets:
            elems.append(Paragraph(f"• {escape(b)}", self.styles['Normal']))
        self._section_data_note(elems)
        elems.append(PageBreak())

    # --------------------- NEW: Competitive Analysis ---------------------
    def competitive_analysis_section(self, elems: List[Any]):
        elems.append(self._section_title("Competitive Analysis"))
        comp = self.competitors if isinstance(self.competitors, dict) else {}
        items = comp.get('items', []) if isinstance(comp.get('items', []), list) else []
        if not items:
            summary = comp.get('summary')
            if summary:
                elems.append(Paragraph(escape(summary), self.styles['Normal']))
            else:
                elems.append(Paragraph("Data Not Collected: No competitor list provided by runner.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return
        rows = [["Competitor", "Performance", "SEO", "Accessibility", "Overall"]]
        for it in items[:6]:
            name = str(it.get('name', it.get('domain', 'Competitor')))
            rows.append([
                name,
                str(it.get('performance', '—')),
                str(it.get('seo', '—')),
                str(it.get('accessibility', '—')),
                str(it.get('overall', '—'))
            ])
        elems.append(self._table(rows, colWidths=[2.4 * inch, 0.9 * inch, 0.9 * inch, 1.0 * inch, 0.9 * inch], header_bg=LIGHT_GRAY_BG))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def crawl_summary_section(self, elems: List[Any]):
        elems.append(self._section_title("Crawl Summary (If Available)"))
        if not self.crawl:
            elems.append(Paragraph("No crawl data detected from runner.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return
        rows = [["Item", "Count"]]
        for k, label in [
            ("internal_urls", "Internal URLs"),
            ("external_urls", "External URLs"),
            ("broken_internal", "Broken internal links"),
            ("broken_external", "Broken external links"),
            ("max_depth", "Max depth crawled"),
        ]:
            if self.crawl.get(k) is not None:
                rows.append([label, str(self.crawl.get(k))])
        elems.append(self._render_clean_table(rows, colWidths=[3.2 * inch, 3.1 * inch], header_bg=LIGHT_GRAY_BG))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def visual_proof_section(self, elems: List[Any]):
        elems.append(self._section_title("Visual Proof of Issues"))
        shots = _load_issue_screenshots(self.assets)
        if not shots:
            elems.append(Paragraph("No issue screenshots detected from runner.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return
        for title, buf in shots[:6]:
            elems.append(Paragraph(escape(title), self.styles['H2']))
            try:
                elems.append(Image(buf, width=5.8 * inch, height=3.3 * inch))
            except Exception:
                elems.append(Paragraph("Screenshot could not be rendered.", self.styles['Muted']))
            elems.append(Spacer(1, 0.08 * inch))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def broken_links_section(self, elems: List[Any]):
        elems.append(self._section_title("Broken Link Analysis"))
        elems.append(Paragraph("Runner did not supply deep crawl link table. Integrate a crawler to populate this section.", self.styles['Muted']))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def analytics_tracking_section(self, elems: List[Any]):
        elems.append(self._section_title("Analytics & Tracking"))
        elems.append(Paragraph("Analytics/Tag detection not supplied by runner. Add GA4/GTM detection in runner to populate.", self.styles['Muted']))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def critical_issues_section(self, elems: List[Any]):
        elems.append(self._section_title("Critical Issues Summary"))
        issues = self.issues
        if not issues:
            elems.append(Paragraph("No critical issues derived from available data.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return
        rows = [["Priority", "Issue", "Category", "Impact", "Recommended Fix"]]
        for i in issues:
            rows.append([i["priority"], i["issue"], i["category"], i["impact"], i["fix"]])
        t = self._table(rows, colWidths=[0.95 * inch, 2.25 * inch, 0.9 * inch, 1.5 * inch, 1.6 * inch], header_bg=ACCENT_BLUE, fontsize=8)
        for r in range(1, len(rows)):
            pr = rows[r][0]
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, r), (0, r), {'🔴 Critical': CRITICAL_RED, '🟠 High': WARNING_ORANGE, '🟡 Medium': YELLOW}.get(pr, SUCCESS_GREEN)),
                ('TEXTCOLOR', (0, r), (0, r), colors.whitesmoke)
            ]))
        elems.append(t)
        self._section_data_note(elems)
        elems.append(PageBreak())

    def recommendations_section(self, elems: List[Any]):
        elems.append(self._section_title("Recommendations & Fix Roadmap"))
        recs: List[Dict[str, str]] = []

        # PSI quick wins
        for o in (self.lh.get("opportunities") or [])[:6] if isinstance(self.lh, dict) else []:
            title = str(o.get("title","")).strip()
            savings_ms = _int_or(o.get("estimated_savings_ms", 0), 0)
            if title and savings_ms:
                recs.append({
                    "item": title,
                    "impact": "High" if savings_ms >= 800 else "Medium",
                    "effort": "Medium",
                    "notes": f"Est. savings: {savings_ms} ms"
                })

        # Accessibility
        axe = self.a11y.get("axe", {}) if isinstance(self.a11y, dict) else {}
        if _int_or(axe.get("counts",{}).get("violations",0),0) > 0:
            recs.append({"item":"Resolve contrast & ARIA violations", "impact":"High", "effort":"Medium", "notes":"WCAG 2.2 AA compliance"})

        # Robots/Sitemap
        if isinstance(self.robots.get("exists"), bool) and not self.robots.get("exists"):
            recs.append({"item":"Add robots.txt", "impact":"Medium", "effort":"Low", "notes":"Add rules & Sitemap URLs"})
        if isinstance(self.sitemap.get("exists"), bool) and not self.sitemap.get("exists"):
            recs.append({"item":"Publish sitemap.xml", "impact":"Medium", "effort":"Low", "notes":"Enable faster discovery"})

        # Security
        if self.secdeep and "content-security-policy" not in (self.secdeep.get("headers") or {}):
            recs.append({"item":"Add CSP header", "impact":"High", "effort":"Medium", "notes":"Mitigate XSS/Injection risk"})
        if self.secdeep and _int_or(self.secdeep.get("mixed_content", 0), 0) > 0:
            recs.append({"item":"Fix mixed content", "impact":"High", "effort":"Low", "notes":"Serve assets via HTTPS only"})

        # Apple-specific hints if auditing Apple
        host = _hostname(self.url or "")
        if host.endswith("apple.com"):
            recs.append({"item":"Adopt AVIF/WebP for hero media (Apple.com)", "impact":"High", "effort":"Medium", "notes":"Reduce LCP weight on homepage hero"})
            recs.append({"item":"Evaluate INP long tasks on product PLP/PDP (Apple.com)", "impact":"High", "effort":"Medium", "notes":"Defer non-critical JS & optimize interaction handlers"})

        # Sort by ROI: High impact + Low effort first
        impact_rank = {"High": 0, "Medium": 1, "Low": 2}
        effort_rank = {"Low": 0, "Medium": 1, "High": 2}
        recs.sort(key=lambda r: (impact_rank.get(r["impact"], 9), effort_rank.get(r["effort"], 9)))

        if not recs:
            elems.append(Paragraph("No recommendations could be derived from available data.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return

        # Compute a simple ROI score for display
        def roi_score(impact: str, effort: str) -> str:
            i = impact_rank.get(impact, 2)
            e = effort_rank.get(effort, 1)
            val = max(1, 10 - (i * 3 + e * 2))
            return str(val)

        rows = [["Recommendation", "Impact", "Effort", "ROI Score", "Details / Notes"]]
        for r in recs[:14]:
            rows.append([r["item"], r["impact"], r["effort"], roi_score(r["impact"], r["effort"]), r["notes"]])
        elems.append(self._table(rows, colWidths=[2.6 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch, 2.0 * inch], header_bg=ACCENT_BLUE, fontsize=8))
        # Benchmark line if provided
        if isinstance(self.bench, dict) and self.bench.get("avg") and self.bench["avg"].get("Performance") is not None:
            elems.append(Spacer(1, 0.06 * inch))
            elems.append(Paragraph(f"Compared to {self.bench.get('industry','industry')} average: {self.bench['avg'].get('Performance')}/100", self.styles['Note']))

        self._section_data_note(elems)
        elems.append(PageBreak())

    # --------------------- NEW: 30-60-90 Day Plan ---------------------
    def plan_30_60_90_section(self, elems: List[Any]):
        elems.append(self._section_title("30-60-90 Day Plan"))
        rows = [["Phase", "Focus", "Examples"]]
        rows.append(["0–30 Days", "High-impact, low-effort fixes", "Compress hero images, defer non-critical JS, add robots/sitemap if missing, fix top a11y issues."])
        rows.append(["30–60 Days", "Performance tuning", "Code-split JS, preconnect critical origins, reduce INP long tasks, strengthen CSP."])
        rows.append(["60–90 Days", "Advanced optimization", "Implement image CDN, field CWV monitoring, UX A/B on CTAs, harden headers enterprise-wide."])
        elems.append(self._table(rows, colWidths=[1.3 * inch, 2.2 * inch, 2.8 * inch], header_bg=LIGHT_GRAY_BG))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def scoring_methodology_section(self, elems: List[Any]):
        elems.append(self._section_title("Scoring Methodology"))
        w = dict(DEFAULT_WEIGHTS)
        if isinstance(self.weights, dict):
            try:
                w.update({k: float(v) for k, v in self.weights.items() if k in w})
            except Exception:
                pass
        rows = [["Category", "Weight"]]
        for k in ["seo", "performance", "security", "accessibility", "ux", "links"]:
            rows.append([k.upper(), f"{int(w[k] * 100)}%"])
        elems.append(self._table(rows, colWidths=[3.2 * inch, 3.1 * inch], header_bg=PALE_BLUE))
        if self.runner_overall != self.overall:
            elems.append(Paragraph(
                f"Runner overall {self.runner_overall}/100 vs computed {self.overall}/100. Charts use computed score for consistency.",
                self.styles['Note']
            ))
        self._section_data_note(elems)
        elems.append(PageBreak())

    # --------------------- NEW: Maturity Index ---------------------
    def maturity_index_section(self, elems: List[Any]):
        elems.append(self._section_title("Website Maturity Index"))
        def level(score: int) -> int:
            s = int(score)
            return 5 if s >= 90 else (4 if s >= 75 else (3 if s >= 60 else (2 if s >= 40 else 1)))
        rows = [["Category", "Level (1–5)"]]
        for k in ["seo", "performance", "security", "accessibility", "ux"]:
            if k in self.scores:
                rows.append([k.upper(), str(level(self.scores.get(k, 0)))])
        elems.append(self._table(rows, colWidths=[3.2 * inch, 3.1 * inch], header_bg=PALE_GREEN))
        self._section_data_note(elems)
        elems.append(PageBreak())

    # --------------------- NEW: Risk Matrix ---------------------
    def risk_matrix_section(self, elems: List[Any]):
        elems.append(self._section_title("Risk Matrix (Impact × Likelihood)"))
        issues = self.issues
        if not issues:
            elems.append(Paragraph("No issues available to plot.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return

        def map_priority(p: str) -> int:
            return {"🔴 Critical": 4, "🟠 High": 3, "🟡 Medium": 2, "🟢 Low": 1}.get(p, 1)

        # Simple likelihood heuristic from category
        def like(cat: str) -> int:
            return {"Security": 3, "Performance": 3, "SEO": 2, "Accessibility": 2}.get(cat, 2)

        xs, ys, labels = [], [], []
        for i in issues[:12]:
            xs.append(like(i.get('category', '')))
            ys.append(map_priority(i.get('priority', '🟢 Low')))
            labels.append(i.get('category', '')[:3].upper())

        fig, ax = plt.subplots(figsize=(4.0, 4.0))
        ax.scatter(xs, ys, c='#C0392B', alpha=0.7)
        for x, y, lbl in zip(xs, ys, labels):
            ax.text(x + 0.03, y + 0.05, lbl, fontsize=8)
        ax.set_xlim(0.5, 3.5); ax.set_ylim(0.5, 4.5)
        ax.set_xticks([1, 2, 3]); ax.set_yticks([1, 2, 3, 4])
        ax.set_xlabel('Likelihood'); ax.set_ylabel('Impact')
        ax.set_title('Risk Matrix')
        ax.grid(True, linestyle='--', alpha=0.3)
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=160, transparent=True)
        plt.close(fig)
        buf.seek(0)
        elems.append(Image(buf, width=3.8 * inch, height=3.8 * inch))
        self._section_data_note(elems)
        elems.append(PageBreak())

    # --------------------- Extended Metrics (optional annex) ---------------------
    def extended_metrics_section(self, elems: List[Any]):
        if os.getenv('PDF_INCLUDE_EXTENDED', '0') != '1':
            # Skip heavy annex by default
            return
        elems.append(self._section_title("Extended Metrics (Annex)"))
        pairs = _collect_extended_metrics(self.data)
        if not pairs:
            elems.append(Paragraph("No additional metrics detected from runner.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return
        rows = [["Key", "Value"]]
        for k, v in pairs:
            if v is not None and str(v).strip() != "":
                rows.append((k, v))
        header = rows[0]
        data_rows = rows[1:]
        if not data_rows:
            elems.append(Paragraph("No additional metrics detected from runner.", self.styles['Muted']))
            self._section_data_note(elems)
            elems.append(PageBreak())
            return
        per_table = 36
        for idx, chunk in enumerate(_chunk(data_rows, per_table)):
            tbl_rows = [header] + chunk
            t = self._table(tbl_rows, colWidths=[2.8 * inch, 3.5 * inch], fontsize=8, header_bg=colors.HexColor("#EEF3FB"))
            elems.append(t)
            if idx < (len(data_rows) - 1) // per_table:
                elems.append(PageBreak())
        self._section_data_note(elems)
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
                if title or body:
                    elems.append(Paragraph(f"<b>{escape(title)}</b>: {escape(body)}", self.styles['Normal']))
        if kv:
            elems.append(Spacer(1, 0.08 * inch))
            elems.append(Paragraph("Key-Value Diagnostics", self.styles['H2']))
            rows = [["Key", "Value"]]
            for pair in kv[:120]:
                k = str(pair.get("key", "")).strip()
                v = str(pair.get("value", "")).strip()
                if k and v:
                    rows.append([k, v])
            if len(rows) > 1:
                elems.append(self._table(rows, colWidths=[2.8 * inch, 3.5 * inch], fontsize=8, header_bg=colors.HexColor("#F7F7F7")))
        elems.append(Spacer(1, 0.08 * inch))
        elems.append(Paragraph(
            "Raw HTTP headers, DOM tree, script/CSS inventories, and third-party requests are not captured by the runner "
            "and therefore omitted here. Integrate a headless fetcher to populate these fields.",
            self.styles['Note']
        ))
        self._section_data_note(elems)
        elems.append(PageBreak())

    def conclusion_section(self, elems: List[Any]):
        elems.append(self._section_title("Conclusion"))
        elems.append(Paragraph(
            "This audit identifies structural, performance, and security improvements required to align the website with "
            "modern web standards and search engine best practices. Addressing the highlighted critical issues will "
            "significantly improve visibility, performance, and risk posture.",
            self.styles['Normal']
        ))
        elems.append(Spacer(1, 0.10 * inch))
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
        self.core_web_vitals_section(elems)
        self.what_we_audited(elems)
        self.website_overview(elems)
        self.industry_benchmark_section(elems)
        self.business_impact_section(elems)
        self.competitive_analysis_section(elems)
        self.seo_section(elems)
        self.performance_section(elems)
        self.security_section(elems)
        self.accessibility_section(elems)
        self.ux_section(elems)
        self.crawl_summary_section(elems)     # optional
        self.visual_proof_section(elems)      # optional
        self.broken_links_section(elems)
        self.analytics_tracking_section(elems)
        self.critical_issues_section(elems)
        self.recommendations_section(elems)
        self.plan_30_60_90_section(elems)
        self.scoring_methodology_section(elems)
        self.maturity_index_section(elems)
        self.risk_matrix_section(elems)
        self.extended_metrics_section(elems)  # optional annex, gated by env
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
      audit_data['history'], audit_data['competitors'], audit_data['field_cwv']
    """
    report = PDFReport(audit_data)
    return report.build_pdf_bytes()
