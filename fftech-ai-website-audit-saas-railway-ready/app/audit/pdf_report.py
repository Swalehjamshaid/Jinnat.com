# -*- coding: utf-8 -*-

import io
import os
import re
import json
import time
import hashlib
import datetime as dt
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
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
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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
    "ux": 0.10,
}

PRIMARY_OK = colors.HexColor("#2ecc71")
PRIMARY_WARN = colors.HexColor("#f39c12")
PRIMARY_BAD = colors.HexColor("#e74c3c")
GRID = colors.HexColor("#DDE1E6")

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# =========================================================
# BRANDING
# =========================================================

def get_branding(client_config: Dict[str, Any]):
    return {
        "company_name": client_config.get("company_name", "FF Tech"),
        "primary_color": client_config.get("primary_color", "#2c3e50"),
        "logo_path": client_config.get("logo_path", None)
    }


# =========================================================
# OPTIONAL: Lighthouse (best-effort)
# =========================================================

def fetch_lighthouse_data(url: str, api_key: str = None) -> Dict[str, Any]:
    try:
        endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {"url": url, "strategy": "desktop"}
        if api_key:
            params["key"] = api_key
        resp = requests.get(endpoint, params=params, timeout=20)
        data = resp.json()
        cats = data.get("lighthouseResult", {}).get("categories", {})
        audits = data.get("lighthouseResult", {}).get("audits", {}) or {}
        # CWV (if available)
        lcp = audits.get("largest-contentful-paint", {}).get("numericValue")
        cls = audits.get("cumulative-layout-shift", {}).get("numericValue")
        inp = audits.get("interactive", {}).get("numericValue")  # not exactly INP, but better than nothing
        return {
            "performance": cats.get("performance", {}).get("score", 0) * 100,
            "seo": cats.get("seo", {}).get("score", 0) * 100,
            "accessibility": cats.get("accessibility", {}).get("score", 0) * 100,
            "lcp_ms": float(lcp) if lcp is not None else None,
            "cls": float(cls) if cls is not None else None,
            "inp_ms": float(inp) if inp is not None else None,
        }
    except Exception:
        return {k: 0 for k in WEIGHTAGE}


# =========================================================
# LIVE SITE AUDIT
# =========================================================

def _fetch(url: str, timeout: int = 12) -> requests.Response:
    return requests.get(url, timeout=timeout, headers={"User-Agent": DEFAULT_UA}, allow_redirects=True)

def _is_same_domain(root: str, link: str) -> bool:
    try:
        rp, lp = urlparse(root), urlparse(link)
        return (rp.netloc.lower() == lp.netloc.lower()) and (lp.scheme in ("http", "https"))
    except Exception:
        return False

def _text_visible(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.extract()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _detect_cdn(headers: Dict[str, str]) -> str:
    hlower = {k.lower(): v for k, v in headers.items()}
    hints = [
        ("cf-ray", "Cloudflare"),
        ("cf-cache-status", "Cloudflare"),
        ("x-amz-cf-id", "AWS CloudFront"),
        ("x-amz-cf-pop", "AWS CloudFront"),
        ("server", hlower.get("server", "")),
        ("x-fastly-request-id", "Fastly"),
        ("x-akamai-transformed", "Akamai"),
        ("akamai-grn", "Akamai"),
        ("x-cache", hlower.get("x-cache", "")),
    ]
    for k, name in hints:
        if k in hlower:
            n = name or hlower.get(k, "")
            if n:
                return str(n)[:40]
    return "Unknown/No signal"

def _robots_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}/robots.txt"

def _safe_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""

def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except Exception:
        return 0.0

def _status_from_score(s: float) -> str:
    s = float(s)
    if s >= 85: return "Good"
    if s >= 65: return "Warning"
    return "Critical"

def audit_live_site(url: str, link_sample: int = 12) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": False
    }
    if not url:
        return result

    try:
        t0 = time.time()
        r = _fetch(url, timeout=16)
        ttfb_ms = r.elapsed.total_seconds() * 1000.0
        page_size_bytes = len(r.content or b"")
        content_type = r.headers.get("content-type", "")
        compressed = r.headers.get("content-encoding") in ("gzip", "br", "deflate")
        cdn = _detect_cdn(r.headers)

        soup = BeautifulSoup(r.text, "html.parser")
        title = (soup.find("title").get_text(strip=True) if soup.find("title") else "")
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        meta_desc = (meta_desc_tag.get("content") if meta_desc_tag else "")
        canonical = soup.find("link", rel=lambda x: x and "canonical" in x)
        canonical_url = canonical.get("href") if canonical else ""
        viewport = soup.find("meta", attrs={"name": "viewport"})
        has_viewport = True if viewport and ("width" in (viewport.get("content") or "").lower()) else False

        h1 = len(soup.find_all("h1"))
        h2 = len(soup.find_all("h2"))
        h3 = len(soup.find_all("h3"))

        imgs = soup.find_all("img")
        img_with_alt = sum(1 for im in imgs if (im.get("alt") is not None and im.get("alt") != ""))
        img_alt_coverage = round(100.0 * (img_with_alt / max(1, len(imgs))), 2)

        aria_missing = 0
        for el in soup.find_all(True):
            # Count elements likely to require ARIA but missing (heuristic)
            if el.name in ("button", "a", "input") and not any(k.startswith("aria-") for k in el.attrs.keys()):
                aria_missing += 1

        schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        has_schema = True if schema_scripts else False

        links = soup.find_all("a", href=True)
        internal_links = []
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        for a in links:
            href = a.get("href")
            if href is None:
                continue
            abs_url = urljoin(root, href)
            if _is_same_domain(root, abs_url):
                internal_links.append(abs_url)

        # sample internal links for 404 detection
        sample = []
        seen = set()
        for l in internal_links:
            if l not in seen:
                sample.append(l)
                seen.add(l)
            if len(sample) >= link_sample:
                break

        broken = 0
        for l in sample:
            try:
                # HEAD first (fallback to GET)
                rr = requests.head(l, timeout=5, headers={"User-Agent": DEFAULT_UA}, allow_redirects=True)
                st = rr.status_code
                if st >= 400:
                    # try GET as some servers do not support HEAD well
                    rr2 = _fetch(l, timeout=6)
                    st = rr2.status_code
                if st >= 400:
                    broken += 1
            except Exception:
                broken += 1

        # robots & sitemap
        robots_ok, sitemap_declared = False, False
        try:
            rob = requests.get(_robots_url(url), timeout=8, headers={"User-Agent": DEFAULT_UA})
            if rob.status_code == 200:
                robots_ok = True
                sitemap_declared = ("sitemap:" in rob.text.lower())
        except Exception:
            pass

        # Security headers
        hdr = r.headers
        tls_https = url.lower().startswith("https")
        has_hsts = ("strict-transport-security" in {k.lower(): v for k, v in hdr.items()})
        has_csp = ("content-security-policy" in {k.lower(): v for k, v in hdr.items()})
        has_xfo = ("x-frame-options" in {k.lower(): v for k, v in hdr.items()})
        has_xss = ("x-xss-protection" in {k.lower(): v for k, v in hdr.items()})

        # counts
        script_count = len(soup.find_all("script"))
        css_count = len(soup.find_all("link", attrs={"rel": "stylesheet"}))
        img_count = len(imgs)

        # Visible text & quick keyword stats
        visible_text = _text_visible(soup)
        words = re.findall(r"[A-Za-z0-9_-]{3,}", visible_text.lower())
        top_terms = {}
        for w in words:
            top_terms[w] = top_terms.get(w, 0) + 1
        top_terms_sorted = sorted(top_terms.items(), key=lambda x: x[1], reverse=True)[:15]

        # Derive category scores (0..100) from heuristics if not provided:
        perf_score = 100.0
        # TTFB
        if ttfb_ms > 1500: perf_score -= 35
        elif ttfb_ms > 800: perf_score -= 20
        elif ttfb_ms > 400: perf_score -= 10
        # Page size
        mb = page_size_bytes / (1024 * 1024)
        if mb > 6: perf_score -= 35
        elif mb > 3: perf_score -= 20
        elif mb > 1.5: perf_score -= 10
        # Requests
        req_penalty = max(0, (script_count + css_count + img_count) - 120) * 0.2
        perf_score -= req_penalty
        # Compression/CDN
        if not compressed: perf_score -= 10
        if cdn == "Unknown/No signal": perf_score -= 5
        perf_score = _clamp(perf_score)

        seo_score = 100.0
        if not title: seo_score -= 25
        if not meta_desc: seo_score -= 20
        if h1 != 1: seo_score -= 10
        if not robots_ok: seo_score -= 10
        if not sitemap_declared: seo_score -= 5
        if broken > 0: seo_score -= min(25, broken * 3)
        if not canonical_url: seo_score -= 5
        if not has_schema: seo_score -= 5
        seo_score = _clamp(seo_score)

        acc_score = 100.0
        if img_count > 0 and img_alt_coverage < 80: acc_score -= 25
        if aria_missing > 10: acc_score -= 15
        # Can't compute contrast reliably without rendering—leave as-is
        acc_score = _clamp(acc_score)

        ux_score = 100.0
        if not has_viewport: ux_score -= 30
        if broken > 0: ux_score -= min(20, broken * 2)
        # forms validation errors not measured—heuristic only
        ux_score = _clamp(ux_score)

        sec_score = 100.0
        if not tls_https: sec_score -= 40
        if tls_https and not has_hsts: sec_score -= 10
        if not has_csp: sec_score -= 20
        if not has_xfo: sec_score -= 10
        if not has_xss: sec_score -= 5
        sec_score = _clamp(sec_score)

        result.update({
            "ok": True,
            "ttfb_ms": round(ttfb_ms, 2),
            "page_weight_mb": round(page_size_bytes / (1024 * 1024), 2),
            "compressed": "Yes" if compressed else "No",
            "cdn": cdn,
            "content_type": content_type,
            "title": title,
            "meta_description_present": "Yes" if meta_desc else "No",
            "canonical_url": canonical_url,
            "viewport_present": "Yes" if has_viewport else "No",
            "h1_count": h1,
            "h2_count": h2,
            "h3_count": h3,
            "img_count": img_count,
            "img_alt_coverage_pct": img_alt_coverage,
            "aria_missing_count": aria_missing,
            "schema_org_present": "Yes" if has_schema else "No",
            "robots_present": "Yes" if robots_ok else "No",
            "sitemap_declared": "Yes" if sitemap_declared else "No",
            "script_count": script_count,
            "css_count": css_count,
            "internal_links_sampled": len(sample),
            "broken_links_detected": broken,
            "security_headers": {
                "https_tls": "Yes" if tls_https else "No",
                "hsts": "Yes" if has_hsts else "No",
                "csp": "Yes" if has_csp else "No",
                "x_frame_options": "Yes" if has_xfo else "No",
                "x_xss_protection": "Yes" if has_xss else "No",
            },
            "top_terms": top_terms_sorted,
            "scores": {
                "performance": perf_score,
                "seo": seo_score,
                "accessibility": acc_score,
                "ux": ux_score,
                "security": sec_score,
            }
        })
    except Exception:
        result["ok"] = False

    return result


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

def line_chart(points: List[Tuple[str, float]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    if not points:
        return _empty_chart("No data")
    labels = [p[0] for p in points]
    values = [float(p[1]) for p in points]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.plot(labels, values, marker="o", color="#0F62FE")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=25, ha="right")
    return _fig_to_buf()

def bar_chart(items: List[Tuple[str, float]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    if not items:
        return _empty_chart("No data")
    labels = [i[0] for i in items]
    values = [float(i[1]) for i in items]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.bar(labels, values, color="#27AE60")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=25, ha="right")
    return _fig_to_buf()

def pie_chart(parts: List[Tuple[str, float]], title: str = "") -> io.BytesIO:
    if not parts:
        return _empty_chart("No data")
    labels = [p[0] for p in parts]
    sizes = [max(0.0, float(p[1])) for p in parts]
    total = sum(sizes)
    if total <= 0:
        sizes = [1.0 for _ in sizes]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140)
    ax.axis("equal")
    ax.set_title(title)
    return _fig_to_buf()

def radar_chart(categories: List[str], values: List[float], title: str = "") -> io.BytesIO:
    if not categories or not values:
        return _empty_chart("No data")
    N = len(categories)
    vals = [float(v) for v in values[:N]]
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    vals += vals[:1]
    angles += angles[:1]
    fig = plt.figure(figsize=(5.4, 4.8))
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), categories)
    ax.set_ylim(0, 100)
    ax.plot(angles, vals, color="#2F80ED", linewidth=2)
    ax.fill(angles, vals, color="#2F80ED", alpha=0.2)
    ax.set_title(title, y=1.08)
    return _fig_to_buf()

def _empty_chart(msg: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.axis("off")
    ax.text(0.5, 0.5, msg, ha="center", va="center")
    return _fig_to_buf()


# =========================================================
# SIGNATURE & PPT
# =========================================================

def generate_digital_signature(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def generate_executive_ppt(audit_data: Dict[str, Any], file_path: str):
    prs = Presentation()
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Executive Audit Summary"
    content = slide.placeholders[1]
    content.text = f"Overall Score: {audit_data.get('overall_score', 0)}"
    prs.save(file_path)


# =========================================================
# DOC + TOC + HEADER/FOOTER
# =========================================================

class _DocWithTOC(SimpleDocTemplate):
    def __init__(self, *args, **kwargs):
        self._heading_styles = {"Heading1": 0, "Heading2": 1}
        super().__init__(*args, **kwargs)

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style_name = getattr(flowable.style, "name", "")
            if style_name in self._heading_styles:
                level = self._heading_styles[style_name]
                text = flowable.getPlainText()
                key = f"h_{hash((text, self.page))}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
                self.notify("TOCEntry", (level, text, self.page))

def _draw_header_footer(c: canvas.Canvas, doc: SimpleDocTemplate, url: str, branding: Dict[str, Any]):
    c.saveState()
    c.setStrokeColor(colors.HexColor(branding.get("primary_color", "#2c3e50")))
    c.setLineWidth(0.6)
    c.line(doc.leftMargin, doc.height + doc.topMargin + 6, doc.width + doc.leftMargin, doc.height + doc.topMargin + 6)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#525252"))
    header = f"{branding.get('company_name', 'FF Tech')} — {url or ''}"
    c.drawString(doc.leftMargin, doc.height + doc.topMargin + 10, header[:140])
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#6F6F6F"))
    ts = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    page_num = c.getPageNumber()
    c.drawString(doc.leftMargin, doc.bottomMargin - 20, f"Generated: {ts}")
    pr = f"Page {page_num}"
    w = c.stringWidth(pr, "Helvetica", 8)
    c.drawString(doc.leftMargin + doc.width - w, doc.bottomMargin - 20, pr)
    c.restoreState()


# =========================================================
# MAIN (SIGNATURE UNCHANGED)
# =========================================================

def generate_audit_pdf(audit_data: Dict[str, Any],
                       client_config: Dict[str, Any] = None,
                       history_scores: List[float] = None) -> bytes:

    branding = get_branding(client_config or {})
    url = audit_data.get("url", "")
    tool_version = audit_data.get("tool_version", "v1.0")
    lighthouse_key = audit_data.get("google_api_key")  # optional

    # Live audit (fills metrics)
    live = audit_live_site(url)

    # Optional Lighthouse to enrich where available
    lh = {}
    if url:
        try:
            lh = fetch_lighthouse_data(url, lighthouse_key)
        except Exception:
            lh = {}

    # Compute category & overall scores (prefer provided, else live-derived, else Lighthouse)
    scores = {}
    for k in WEIGHTAGE:
        if audit_data.get(k) is not None:
            scores[k] = _clamp(audit_data.get(k))
        elif live.get("scores", {}).get(k) is not None:
            scores[k] = _clamp(live["scores"][k])
        elif lh.get(k) is not None:
            scores[k] = _clamp(lh[k])
        else:
            scores[k] = 0.0

    overall = round(sum(scores[k] * WEIGHTAGE[k] for k in WEIGHTAGE), 2)

    # Build PDF
    buf = io.BytesIO()
    doc = _DocWithTOC(
        buf, pagesize=A4,
        leftMargin=36, rightMargin=36, topMargin=54, bottomMargin=54,
        title="FF Tech Web Audit", author=branding.get("company_name", "FF Tech")
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="KPIHeader", parent=styles["Heading2"],
                              textColor=colors.HexColor(branding.get("primary_color", "#2c3e50"))))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9))
    styles.add(ParagraphStyle(name="Tiny", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6F6F6F")))
    elements: List[Any] = []

    # 1) Cover
    logo_path = branding.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        try:
            elements.append(Image(logo_path, width=1.6 * inch, height=1.6 * inch))
        except Exception:
            pass
    elements.append(Paragraph(branding["company_name"], styles["Title"]))
    elements.append(Spacer(1, 0.12 * inch))
    elements.append(Paragraph("FF Tech Web Audit Report", styles["Heading1"]))
    elements.append(Spacer(1, 0.06 * inch))
    elements.append(Paragraph(f"Website: {url or 'Not provided'}", styles["Normal"]))
    elements.append(Paragraph(f"Domain: {_safe_domain(url)}", styles["Small"]))
    elements.append(Paragraph(f"Report Time (UTC): {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elements.append(Paragraph(f"Audit/Tool Version: {tool_version}", styles["Normal"]))
    elements.append(Spacer(1, 0.12 * inch))
    dashboard_link = audit_data.get("dashboard_url") or url
    if dashboard_link:
        try:
            code = qr.QrCodeWidget(dashboard_link)
            bx = code.getBounds()
            w = bx[2] - bx[0]; h = bx[3] - bx[1]
            d = Drawing(1.4 * inch, 1.4 * inch, transform=[1.4 * inch / w, 0, 0, 1.4 * inch / h, 0, 0])
            d.add(code)
            elements.append(d)
            if "Caption" in styles:
                elements.append(Paragraph("Scan to view the online audit/dashboard", styles["Caption"]))
        except Exception:
            pass
    elements.append(PageBreak())

    # 3) TOC
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(fontName="Helvetica-Bold", name="TOCHeading1", fontSize=12, leftIndent=20, firstLineIndent=-10, spaceBefore=6),
        ParagraphStyle(fontName="Helvetica", name="TOCHeading2", fontSize=10, leftIndent=36, firstLineIndent=-10, spaceBefore=2),
    ]
    elements.append(Paragraph("Table of Contents", styles["Heading1"]))
    elements.append(Spacer(1, 0.08 * inch))
    elements.append(toc)
    elements.append(PageBreak())

    # 2) Executive Summary
    elements.append(Paragraph("Executive Summary", styles["Heading1"]))
    elements.append(Spacer(1, 0.06 * inch))
    elements.append(Paragraph(f"Overall Website Health Score: <b>{overall}</b>/100", styles["Normal"]))

    cat_rows = [["Category", "Score", "Status"]]
    for k in WEIGHTAGE:
        s = scores.get(k, 0)
        cat_rows.append([k.capitalize(), f"{s:.0f}", _status_from_score(s)])
    # Optional extra categories if provided by audit
    if "traffic_score" in audit_data:
        ts = _clamp(audit_data["traffic_score"])
        cat_rows.append(["Traffic & Engagement", f"{ts:.0f}", _status_from_score(ts)])
    if "mobile" in audit_data:
        ms = _clamp(audit_data["mobile"])
        cat_rows.append(["Mobile Responsiveness", f"{ms:.0f}", _status_from_score(ms)])

    table = Table(cat_rows, colWidths=[3.1 * inch, 1.0 * inch, 1.6 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#121619")),
        ("GRID", (0,0), (-1,-1), 0.25, GRID),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.10 * inch))

    # Trend summary (history_scores)
    if history_scores:
        img = line_chart([(str(i+1), float(v)) for i, v in enumerate(history_scores)], "Overall Score Trend", "Period", "Score")
        elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))

    # AI Recommendations (summary)
    elements.append(Spacer(1, 0.12 * inch))
    elements.append(Paragraph("AI-Generated Recommendations (Summary)", styles["KPIHeader"]))
    for rec in _collect_ai_recommendations(live, scores):
        elements.append(Paragraph(f"- {rec}", styles["Normal"]))
    elements.append(PageBreak())

    # 4) Traffic & Google Search Metrics
    elements.append(Paragraph("Traffic & Google Search Metrics", styles["Heading1"]))
    traffic = audit_data.get("traffic") or {}
    gsc = audit_data.get("gsc") or {}
    if not traffic:
        elements.append(Paragraph("Google Analytics/GA4 data not available (no credentials/data provided).", styles["Small"]))
    else:
        if isinstance(traffic.get("trend"), list) and traffic["trend"]:
            try:
                pts = [(str(p[0]), float(p[1])) for p in traffic["trend"]]
                img = line_chart(pts, "Traffic Trend (6–12 months)", "Period", "Visits")
                elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
            except Exception:
                pass
        if isinstance(traffic.get("sources"), dict) and traffic["sources"]:
            try:
                parts = [(k, float(v)) for k, v in traffic["sources"].items()]
                img = pie_chart(parts, "Traffic Sources")
                elements.append(Image(img, width=4.8 * inch, height=4.8 * inch))
            except Exception:
                pass
        ga_rows = []
        def _ga(label, key): 
            v = traffic.get(key); 
            ga_rows.append([label, str(v) if v is not None else "N/A"])
        for label, key in [
            ("Total Visitors", "total_visitors"),
            ("Organic Traffic", "organic"),
            ("Direct", "direct"),
            ("Referral", "referral"),
            ("Social", "social"),
            ("Paid", "paid"),
            ("Bounce Rate (%)", "bounce_rate"),
            ("Avg. Session Duration (s)", "avg_session_duration"),
            ("Pageviews per Session", "pages_per_session"),
        ]: _ga(label, key)
        elements.append(_mini_table(["Metric", "Value"], ga_rows))

    if not gsc:
        elements.append(Paragraph("Google Search Console data not available (no credentials/data provided).", styles["Small"]))
    else:
        gsc_rows = []
        for label, key in [("Impressions", "impressions"), ("Clicks", "clicks"), ("CTR (%)", "ctr")]:
            v = gsc.get(key)
            gsc_rows.append([label, str(v) if v is not None else "N/A"])
        elements.append(_mini_table(["GSC Metric", "Value"], gsc_rows))
        if isinstance(gsc.get("queries"), list) and gsc["queries"]:
            try:
                top_q = gsc["queries"][:10]
                items = [(str(q.get("query", ""))[:24], float(q.get("clicks", 0))) for q in top_q]
                img = bar_chart(items, "Top Queries by Clicks", "Query", "Clicks")
                elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
            except Exception:
                pass
    elements.append(PageBreak())

    # 5) SEO KPIs
    elements.append(Paragraph("SEO KPIs", styles["Heading1"]))
    seo_rows = _seo_kpis_from_live(live, lh)
    elements.append(_kpi_scorecard_table(seo_rows))
    # Optional: page speed histogram (if supplied)
    if isinstance(audit_data.get("page_speed_hist"), list) and audit_data["page_speed_hist"]:
        try:
            pairs = [(str(b), float(v)) for b, v in audit_data["page_speed_hist"]]
            img = bar_chart(pairs, "Page Speed Histogram (ms buckets)", "Bucket", "Pages")
            elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
        except Exception:
            pass
    elements.append(PageBreak())

    # 6) Performance KPIs
    elements.append(Paragraph("Performance KPIs", styles["Heading1"]))
    perf_rows = _performance_kpis_from_live(live, lh)
    elements.append(_kpi_scorecard_table(perf_rows))
    # Trend (if provided)
    if isinstance(audit_data.get("perf_trend"), list) and audit_data["perf_trend"]:
        try:
            pts = [(str(p[0]), float(p[1])) for p in audit_data["perf_trend"]]
            img = line_chart(pts, "Load Time Trend (ms)", "Period", "ms")
            elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
        except Exception:
            pass
    elements.append(PageBreak())

    # 7) Security KPIs
    elements.append(Paragraph("Security KPIs", styles["Heading1"]))
    sec_rows = _security_kpis_from_live(live)
    elements.append(_kpi_scorecard_table(sec_rows))
    # Severity bar (derived)
    sev_items = _security_severity_bars(live)
    if sev_items:
        img = bar_chart(sev_items, "Security Findings by Severity", "Severity", "Count")
        elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
    # Heatmap (if provided)
    if isinstance(audit_data.get("vuln_heatmap"), dict) and audit_data["vuln_heatmap"]:
        try:
            sev = ["Critical", "High", "Medium", "Low"]
            months = list(audit_data["vuln_heatmap"].keys())[:12]
            matrix = []
            for m in months:
                row = audit_data["vuln_heatmap"][m]
                matrix.append([float(row.get(s, 0)) for s in sev])
            matrix_T = np.array(matrix).T.tolist()
            img = _heatmap(matrix_T, months, sev, "Vulnerability Severity Heatmap")
            elements.append(Image(img, width=6.2 * inch, height=3.6 * inch))
        except Exception:
            pass
    elements.append(PageBreak())

    # 8) Accessibility KPIs
    elements.append(Paragraph("Accessibility KPIs", styles["Heading1"]))
    acc_rows = _accessibility_kpis_from_live(live)
    elements.append(_kpi_scorecard_table(acc_rows))
    # Radar
    acc_radar = {
        "Alt Coverage": live.get("img_alt_coverage_pct", 0),
        "ARIA Coverage": max(0.0, 100.0 - min(100.0, live.get("aria_missing_count", 0) * 5.0)),
        "Structure (H1/H2/H3)": 100.0 if live.get("h1_count") == 1 else 70.0,
        "Viewport": 100.0 if live.get("viewport_present") == "Yes" else 40.0
    }
    img = radar_chart(list(acc_radar.keys()), list(acc_radar.values()), "Accessibility Radar")
    elements.append(Image(img, width=5.2 * inch, height=4.8 * inch))
    elements.append(PageBreak())

    # 9) UX KPIs
    elements.append(Paragraph("UX / User Experience KPIs", styles["Heading1"]))
    ux_rows = _ux_kpis_from_live(live)
    elements.append(_kpi_scorecard_table(ux_rows))
    ux_radar = {
        "Mobile": 100.0 if live.get("viewport_present") == "Yes" else 40.0,
        "Broken Links": max(0.0, 100.0 - min(100.0, live.get("broken_links_detected", 0) * 8.0)),
        "Readability (proxy)": 70.0,  # placeholder proxy; keep displayed & constant
        "Interactivity (proxy)": 70.0
    }
    img = radar_chart(list(ux_radar.keys()), list(ux_radar.values()), "UX Radar")
    elements.append(Image(img, width=5.2 * inch, height=4.8 * inch))
    elements.append(PageBreak())

    # 10) Competitor Comparison
    elements.append(Paragraph("Competitor Comparison", styles["Heading1"]))
    competitors = audit_data.get("competitors") or []
    if competitors:
        series = {}
        for comp in competitors[:5]:
            name = comp.get("name") or comp.get("domain") or "Competitor"
            trend = comp.get("traffic_trend") or []
            series[name] = [(str(p[0]), float(p[1])) for p in trend][:12]
        if series:
            img = _multi_line_chart(series, "Traffic vs Competitors", "Period", "Traffic")
            elements.append(Image(img, width=6.2 * inch, height=3.6 * inch))
        seo_comp = [(str((c.get("name") or c.get("domain") or "Comp"))[:22], float(c.get("seo", 0))) for c in competitors[:5]]
        if seo_comp:
            img = bar_chart(seo_comp, "SEO Performance (Score)", "Competitor", "Score")
            elements.append(Image(img, width=6.2 * inch, height=3.6 * inch))
    else:
        elements.append(Paragraph("Not available (no competitor data provided).", styles["Small"]))
    elements.append(PageBreak())

    # 11) Historical Comparison / Trend Analysis
    elements.append(Paragraph("Historical Comparison / Trend Analysis", styles["Heading1"]))
    hist = audit_data.get("history") or {}
    for key, label, ylabel in [
        ("traffic", "Traffic Trend", "Traffic"),
        ("keyword_rank", "Keyword Ranking Trend", "Avg Rank"),
        ("page_speed", "Page Speed Trend (ms)", "ms"),
        ("sec_vulns", "Security Vulnerabilities Trend", "Count"),
        ("engagement", "Engagement Trend (Pages/Session)", "Pages/Session"),
    ]:
        if key in hist and isinstance(hist[key], list) and hist[key]:
            try:
                pts = [(str(p[0]), float(p[1])) for p in hist[key]][:12]
                img = line_chart(pts, label, "Period", ylabel)
                elements.append(Image(img, width=5.8 * inch, height=3.2 * inch))
            except Exception:
                pass
    elements.append(PageBreak())

    # 13) KPI Scorecards (Consolidated)
    elements.append(Paragraph("KPI Scorecards (Consolidated)", styles["Heading1"]))
    consolidated = _consolidate_kpis(seo_rows, perf_rows, sec_rows, acc_rows, ux_rows)
    if consolidated:
        elements.append(_kpi_scorecard_table(consolidated, show_weight=True, show_link=False))
    else:
        elements.append(Paragraph("No consolidated KPI scorecard available.", styles["Small"]))
    elements.append(PageBreak())

    # 14) AI Recommendations (Detailed)
    elements.append(Paragraph("AI Recommendations (Detailed)", styles["Heading1"]))
    detailed_recs = _collect_ai_recommendations(live, scores)
    for r in detailed_recs:
        elements.append(Paragraph(f"- {r}", styles["Normal"]))

    # Build with header/footer
    def _first(c, d): _draw_header_footer(c, d, url, branding)
    def _later(c, d): _draw_header_footer(c, d, url, branding)
    doc.build(elements, onFirstPage=_first, onLaterPages=_later)

    # Signature + optional PPT
    pdf_bytes = buf.getvalue()
    buf.close()
    print("Digital Signature:", generate_digital_signature(pdf_bytes))
    try:
        generate_executive_ppt({"overall_score": overall}, "/tmp/executive_summary.pptx")
    except Exception:
        pass

    return pdf_bytes


# =========================================================
# TABLE / KPI HELPERS
# =========================================================

def _mini_table(headers: List[str], rows: List[List[Any]]) -> Table:
    data = [headers] + rows
    t = Table(data, colWidths=[2.6 * inch, 2.0 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, GRID),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t

def _kpi_scorecard_table(rows: List[Dict[str, Any]], show_weight: bool = False, show_link: bool = False) -> Table:
    headers = ["KPI Name", "Value", "Status"]
    col_widths = [3.1 * inch, 1.1 * inch, 1.0 * inch]
    if show_weight:
        headers.append("Weight")
        col_widths.append(0.9 * inch)
    if show_link:
        headers.append("Link")
        col_widths.append(1.3 * inch)

    data = [headers]
    for r in rows:
        name = str(r.get("name", ""))
        value = r.get("value", "")
        status = str(r.get("status", ""))
        weight = r.get("weight", "")
        link = r.get("link", "")
        row = [name, str(value), status]
        if show_weight:
            row.append(f"{weight}" if isinstance(weight, (int, float)) else str(weight or ""))
        if show_link:
            row.append(str(link)[:60] if link else "")
        data.append(row)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    styles = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#121619")),
        ("GRID", (0, 0), (-1, -1), 0.25, GRID),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
    ]
    # Color-code status column
    for r_i in range(1, len(data)):
        try:
            status = (data[r_i][2] or "").strip().lower()
            if status.startswith("good"):
                styles.append(("TEXTCOLOR", (2, r_i), (2, r_i), PRIMARY_OK))
            elif status.startswith("warn"):
                styles.append(("TEXTCOLOR", (2, r_i), (2, r_i), PRIMARY_WARN))
            else:
                styles.append(("TEXTCOLOR", (2, r_i), (2, r_i), PRIMARY_BAD))
        except Exception:
            pass
    t.setStyle(TableStyle(styles))
    return t

def _seo_kpis_from_live(live: Dict[str, Any], lh: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    def add(n, v, s): rows.append({"name": n, "value": v, "status": s})

    # Live checks
    add("Title Tag Present", live.get("title") != "", "Good" if live.get("title") else "Critical")
    add("Meta Description Present", live.get("meta_description_present", "No"), "Good" if live.get("meta_description_present") == "Yes" else "Warning")
    add("Canonical Tag Present", "Yes" if live.get("canonical_url") else "No", "Good" if live.get("canonical_url") else "Warning")
    add("H1 Count", live.get("h1_count", 0), "Good" if live.get("h1_count", 0) == 1 else "Warning")
    add("H2 Count", live.get("h2_count", 0), "Good" if live.get("h2_count", 0) >= 1 else "Warning")
    add("H3 Count", live.get("h3_count", 0), "Good" if live.get("h3_count", 0) >= 1 else "Warning")
    add("robots.txt Present", live.get("robots_present", "No"), "Good" if live.get("robots_present") == "Yes" else "Warning")
    add("Sitemap Declared", live.get("sitemap_declared", "No"), "Good" if live.get("sitemap_declared") == "Yes" else "Warning")
    add("Broken Links (sample)", live.get("broken_links_detected", 0), "Good" if live.get("broken_links_detected", 0) == 0 else "Warning")
    add("Image Alt Coverage (%)", live.get("img_alt_coverage_pct", 0), "Good" if live.get("img_alt_coverage_pct", 0) >= 80 else "Warning")
    add("Structured Data (Schema.org)", live.get("schema_org_present", "No"), "Good" if live.get("schema_org_present") == "Yes" else "Warning")

    # Lighthouse CWV if present
    if lh.get("lcp_ms") is not None:
        add("LCP (ms)", round(lh["lcp_ms"]), "Good" if lh["lcp_ms"] <= 2500 else "Warning")
    if lh.get("cls") is not None:
        add("CLS", round(lh["cls"], 3), "Good" if lh["cls"] <= 0.1 else "Warning")
    if lh.get("inp_ms") is not None:
        add("Interactive (ms)", round(lh["inp_ms"]), "Good" if lh["inp_ms"] <= 2000 else "Warning")

    return rows[:40]

def _performance_kpis_from_live(live: Dict[str, Any], lh: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    def add(n, v, s): rows.append({"name": n, "value": v, "status": s})

    add("Time To First Byte (ms)", live.get("ttfb_ms", "N/A"), "Good" if live.get("ttfb_ms", 0) <= 800 else "Warning")
    add("Page Weight (MB)", live.get("page_weight_mb", "N/A"), "Good" if live.get("page_weight_mb", 0) <= 3 else "Warning")
    add("Compression (gzip/brotli)", live.get("compressed", "No"), "Good" if live.get("compressed") == "Yes" else "Warning")
    add("CDN Detected", live.get("cdn", "Unknown"), "Good" if live.get("cdn") != "Unknown/No signal" else "Warning")
    add("Scripts (count)", live.get("script_count", 0), "Good" if live.get("script_count", 0) <= 60 else "Warning")
    add("Stylesheets (count)", live.get("css_count", 0), "Good" if live.get("css_count", 0) <= 15 else "Warning")
    add("Images (count)", live.get("img_count", 0), "Good" if live.get("img_count", 0) <= 120 else "Warning")

    # If Lighthouse perf exists, show it
    if lh.get("performance") is not None:
        add("Lighthouse Performance Score", round(lh["performance"]), "Good" if lh["performance"] >= 85 else "Warning")

    return rows[:20]

def _security_kpis_from_live(live: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    def add(n, v, s): rows.append({"name": n, "value": v, "status": s})
    sh = live.get("security_headers", {}) or {}

    add("HTTPS / TLS", sh.get("https_tls", "No"), "Good" if sh.get("https_tls") == "Yes" else "Critical")
    add("HSTS Header", sh.get("hsts", "No"), "Good" if sh.get("hsts") == "Yes" else "Warning")
    add("Content-Security-Policy", sh.get("csp", "No"), "Good" if sh.get("csp") == "Yes" else "Warning")
    add("X-Frame-Options", sh.get("x_frame_options", "No"), "Good" if sh.get("x_frame_options") == "Yes" else "Warning")
    add("X-XSS-Protection", sh.get("x_xss_protection", "No"), "Good" if sh.get("x_xss_protection") == "Yes" else "Warning")
    add("Broken Links (proxy risk)", live.get("broken_links_detected", 0), "Good" if live.get("broken_links_detected", 0) == 0 else "Warning")
    # Placeholders for counts if your pipeline fills them:
    for key in ["critical_vulns", "high_vulns", "medium_vulns", "low_vulns"]:
        val = live.get(key)
        if val is not None:
            add(key.replace("_", " ").title(), val, "Warning" if val else "Good")
    return rows[:20]

def _accessibility_kpis_from_live(live: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    def add(n, v, s): rows.append({"name": n, "value": v, "status": s})
    add("Alt Text Coverage (%)", live.get("img_alt_coverage_pct", 0), "Good" if live.get("img_alt_coverage_pct", 0) >= 80 else "Warning")
    add("ARIA Missing (count)", live.get("aria_missing_count", 0), "Good" if live.get("aria_missing_count", 0) <= 10 else "Warning")
    add("Viewport (mobile)", live.get("viewport_present", "No"), "Good" if live.get("viewport_present") == "Yes" else "Warning")
    add("Headings Structure (H1)", live.get("h1_count", 0), "Good" if live.get("h1_count", 0) == 1 else "Warning")
    return rows[:20]

def _ux_kpis_from_live(live: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    def add(n, v, s): rows.append({"name": n, "value": v, "status": s})
    add("Mobile-Friendliness (Viewport)", live.get("viewport_present", "No"), "Good" if live.get("viewport_present") == "Yes" else "Warning")
    add("Broken Links (count)", live.get("broken_links_detected", 0), "Good" if live.get("broken_links_detected", 0) == 0 else "Warning")
    add("Page Weight (MB)", live.get("page_weight_mb", 0), "Good" if live.get("page_weight_mb", 0) <= 3 else "Warning")
    return rows[:20]

def _security_severity_bars(live: Dict[str, Any]) -> List[Tuple[str, float]]:
    # Map missing headers to severities for a simple derived bar chart
    sh = live.get("security_headers", {}) or {}
    sev = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    if sh.get("https_tls") != "Yes": sev["Critical"] += 1
    if sh.get("csp") != "Yes": sev["High"] += 1
    if sh.get("hsts") != "Yes": sev["Medium"] += 1
    if sh.get("x_frame_options") != "Yes": sev["Medium"] += 1
    if sh.get("x_xss_protection") != "Yes": sev["Low"] += 1
    return [(k, float(v)) for k, v in sev.items() if v > 0]

def _heatmap(matrix: List[List[float]], xlabels: List[str], ylabels: List[str], title: str) -> io.BytesIO:
    data = np.array(matrix) if matrix else np.zeros((1, 1))
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    c = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(xlabels)))
    ax.set_yticks(range(len(ylabels)))
    ax.set_xticklabels(xlabels, rotation=35, ha="right")
    ax.set_yticklabels(ylabels)
    ax.set_title(title)
    fig.colorbar(c, ax=ax, fraction=0.046, pad=0.04)
    return _fig_to_buf()

def _multi_line_chart(series: Dict[str, List[Tuple[str, float]]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    if not series:
        return _empty_chart("No data")
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    for name, pts in series.items():
        labels = [p[0] for p in pts]
        values = [float(p[1]) for p in pts]
        ax.plot(labels, values, marker="o", linewidth=2, label=name)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=25, ha="right")
    ax.legend()
    return _fig_to_buf()

def _consolidate_kpis(*sections: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for sec in sections:
        for row in (sec or []):
            out.append({
                "name": row.get("name", ""),
                "value": row.get("value", ""),
                "status": row.get("status", "")
            })
    return out[:150]

def _collect_ai_recommendations(live: Dict[str, Any], scores: Dict[str, float]) -> List[str]:
    recs: List[str] = []
    def add(msg): 
        if msg not in recs: 
            recs.append(msg)

    # SEO
    if live.get("title", "") == "" or live.get("meta_description_present") != "Yes":
        add("Add or improve <title> and meta description for better relevance and CTR.")
    if live.get("h1_count", 0) != 1:
        add("Ensure a single, descriptive H1 per page; organize H2/H3 for structure.")
    if live.get("broken_links_detected", 0) > 0:
        add("Fix broken internal links to improve crawlability and UX.")
    if live.get("schema_org_present") != "Yes":
        add("Implement structured data (Schema.org) on key templates.")

    # Performance
    if live.get("ttfb_ms", 0) > 800 or live.get("page_weight_mb", 0) > 3:
        add("Optimize server TTFB and reduce page weight (image compression, lazy-loading, code splitting).")
    if live.get("compressed") != "Yes":
        add("Enable brotli/gzip compression and HTTP/2/3 where possible.")
    if live.get("cdn", "Unknown") == "Unknown/No signal":
        add("Use a CDN for global delivery and better caching performance.")

    # Security
    sh = live.get("security_headers", {}) or {}
    if sh.get("https_tls") != "Yes" or sh.get("hsts") != "Yes":
        add("Enforce HTTPS with HSTS to prevent protocol downgrade/SSL stripping.")
    if sh.get("csp") != "Yes":
        add("Set a strict Content-Security-Policy (script-src/style-src) to mitigate XSS.")
    if sh.get("x_frame_options") != "Yes":
        add("Set X-Frame-Options or frame-ancestors in CSP to prevent clickjacking.")

    # Accessibility
    if live.get("img_alt_coverage_pct", 100) < 80 or live.get("aria_missing_count", 0) > 10:
        add("Increase alt text coverage and add appropriate ARIA attributes; test with screen readers.")

    # UX
    if live.get("viewport_present") != "Yes":
        add("Add responsive viewport meta for mobile users.")
    if live.get("broken_links_detected", 0) > 0:
        add("Repair or redirect broken links to reduce friction.")

    return recs[:15]
