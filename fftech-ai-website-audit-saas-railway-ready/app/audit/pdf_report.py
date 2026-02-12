# -*- coding: utf-8 -*-
"""
fftech-ai-website-audit-saas-railway-ready/app/audit/pdf_report.py

Enterprise-grade Web Audit PDF generator (single-file, self-contained)
- Live HTTP fetch & DOM analysis (SEO, Performance, Security, A11y, UX proxies)
- Broken-link sampling (internal links)
- Optional PageSpeed Insights highlights (Lighthouse categories) if API key is supplied
- GA/GA4 & GSC ingestion (dicts or CSV paths)
- Competitor inputs & charts
- Extra accessibility checks: color contrast sampling, keyboard/focus heuristics, skip link
- Clickable Table of Contents (H1/H2)
- Color-coded KPI scorecards
- Charts (bar, line, pie, radar) — at least one visual per major page
- Digital certificate page with SHA-256 signature
"""

import io
import os
import re
import csv
import json
import math
import argparse
import hashlib
import datetime as dt
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# ReportLab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.pdfgen import canvas

# Charts
import matplotlib
matplotlib.use("Agg")  # headless-safe
import matplotlib.pyplot as plt
import numpy as np

# =========================================
# CONFIGURATION / BRANDING
# =========================================
COMPANY = "FF Tech"
VERSION = "v3.5-enterprise"

WEIGHTAGE = {
    "performance": 0.30,
    "security":    0.25,
    "seo":         0.20,
    "accessibility":0.15,
    "ux":          0.10,
}

PRIMARY     = colors.HexColor("#2C3E50")
OK_COLOR    = colors.HexColor("#2ECC71")
WARN_COLOR  = colors.HexColor("#F39C12")
BAD_COLOR   = colors.HexColor("#E74C3C")
GRID        = colors.HexColor("#DDE1E6")

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122 Safari/537.36"
)
REQ_HEADERS = {"User-Agent": DEFAULT_UA}

BROKEN_SAMPLE_LIMIT = 20
TIMEOUT = 15  # seconds

# =========================================
# SAFE TEXT FOR REPORTLAB
# =========================================
import html
from xml.sax.saxutils import escape as xml_escape

def rl_safe(text: Any) -> str:
    s = "" if text is None else str(text)
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", "", s)
    return xml_escape(s)

def P(text, style, bullet=None):
    safe = rl_safe(text)
    if bullet:
        return Paragraph(safe, style, bulletText=bullet)
    return Paragraph(safe, style)

# =========================================
# CLICKABLE TOC DOC
# =========================================
class TOCDoc(SimpleDocTemplate):
    def __init__(self, *args, **kwargs):
        self._heading_styles = {"Heading1": 0, "Heading2": 1}
        super().__init__(*args, **kwargs)

    def afterFlowable(self, flowable):
        from reportlab.platypus import Paragraph as RLParagraph
        if isinstance(flowable, RLParagraph):
            style_name = getattr(flowable.style, "name", "")
            if style_name in self._heading_styles:
                level = self._heading_styles[style_name]
                text = flowable.getPlainText()
                page_num = self.canv.getPageNumber()
                key = f"h_{hash((text, page_num))}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
                self.notify("TOCEntry", (level, text, page_num))

def draw_header_footer(c: canvas.Canvas, doc: SimpleDocTemplate, url: str):
    c.saveState()
    # Header line
    c.setStrokeColor(PRIMARY)
    c.setLineWidth(0.6)
    c.line(doc.leftMargin, doc.height + doc.topMargin + 6,
           doc.leftMargin + doc.width, doc.height + doc.topMargin + 6)
    # Header text
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#525252"))
    header = f"{COMPANY} — {url or ''}"
    c.drawString(doc.leftMargin, doc.height + doc.topMargin + 10, header[:140])
    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#6F6F6F"))
    page_num = c.getPageNumber()
    timestamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    c.drawString(doc.leftMargin, doc.bottomMargin - 20, f"Generated: {timestamp}")
    w = c.stringWidth(f"Page {page_num}", "Helvetica", 8)
    c.drawString(doc.leftMargin + doc.width - w, doc.bottomMargin - 20, f"Page {page_num}")
    c.restoreState()

# =========================================
# UTIL: CONTRAST / COLORS
# =========================================
def _parse_css_color(val: str) -> Optional[Tuple[float,float,float]]:
    if not val: return None
    val = val.strip()
    try:
        if val.startswith("#"):
            hexv = val[1:]
            if len(hexv) in (3, 4):
                hexv = "".join([ch*2 for ch in hexv[:3]])
            if len(hexv) >= 6:
                r = int(hexv[0:2], 16)/255.0
                g = int(hexv[2:4], 16)/255.0
                b = int(hexv[4:6], 16)/255.0
                return (r,g,b)
        if val.startswith("rgb"):
            nums = re.findall(r"[\d.]+", val)
            if len(nums) >= 3:
                r, g, b = [min(255, float(n))/255.0 for n in nums[:3]]
                return (r,g,b)
    except:
        return None
    return None

def _rel_luminance(rgb: Tuple[float,float,float]) -> float:
    def _ch(c):
        return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    r, g, b = [_ch(c) for c in rgb]
    return 0.2126*r + 0.7152*g + 0.0722*b

def contrast_ratio(fg_rgb, bg_rgb) -> float:
    if fg_rgb is None or bg_rgb is None: return 0.0
    L1 = _rel_luminance(fg_rgb)
    L2 = _rel_luminance(bg_rgb)
    L1, L2 = max(L1, L2), min(L1, L2)
    return (L1 + 0.05) / (L2 + 0.05)

# =========================================
# LIVE AUDIT HELPERS
# =========================================
def fetch(url: str) -> requests.Response:
    return requests.get(url, timeout=TIMEOUT, headers=REQ_HEADERS, allow_redirects=True)

def is_same_domain(root: str, link: str) -> bool:
    rp, lp = urlparse(root), urlparse(link)
    return (rp.netloc.lower() == lp.netloc.lower()) and (lp.scheme in ("http", "https"))

def detect_cdn(headers: Dict[str, str]) -> str:
    hl = {k.lower(): v for k, v in headers.items()}
    if "cf-ray" in hl or "cf-cache-status" in hl:
        return "Cloudflare"
    if "x-amz-cf-id" in hl or "x-amz-cf-pop" in hl:
        return "AWS CloudFront"
    if "x-fastly-request-id" in hl:
        return "Fastly"
    if "x-akamai-transformed" in hl or "akamai-grn" in hl:
        return "Akamai"
    if "x-cache" in hl and "hit" in str(hl.get("x-cache", "")).lower():
        return "CDN (cache hit)"
    return "Unknown"

def robots_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}/robots.txt"

def audit_site(url: str, link_sample: int = BROKEN_SAMPLE_LIMIT) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False}
    if not url: return out
    try:
        r = fetch(url)
        ttfb_ms = r.elapsed.total_seconds() * 1000.0
        size_mb = round(len(r.content or b"") / (1024*1024), 2)
        compressed = r.headers.get("content-encoding") in ("gzip", "br", "deflate")
        cdn = detect_cdn(r.headers)
        content_type = r.headers.get("content-type", "")

        soup = BeautifulSoup(r.text, "html.parser")
        title = (soup.title.get_text(strip=True) if soup.title else "")
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        meta_desc_present = "Yes" if (meta_desc_tag and meta_desc_tag.get("content")) else "No"
        canonical = soup.find("link", rel=lambda x: x and "canonical" in x)
        canonical_url = canonical.get("href") if canonical else ""
        viewport = soup.find("meta", attrs={"name": "viewport"})
        has_viewport = True if viewport and ("width" in (viewport.get("content") or "").lower()) else False

        h1 = len(soup.find_all("h1"))
        h2 = len(soup.find_all("h2"))
        h3 = len(soup.find_all("h3"))

        imgs = soup.find_all("img")
        alt_cov = round(100.0 * (sum(1 for im in imgs if (im.get("alt") not in (None, ""))) / max(1, len(imgs))), 2) if imgs else 0.0

        aria_missing = 0
        for el in soup.find_all(True):
            if el.name in ("button", "a", "input") and not any(k.startswith("aria-") for k in el.attrs.keys()):
                aria_missing += 1

        # A11y extras: contrast sampling & keyboard heuristics
        contrast_fail = 0; contrast_total = 0
        focus_issues = 0; outline_none_count = 0; has_skip_link = False

        for a in soup.find_all("a", href=True):
            if a.get("href","").startswith("#") and ("main" in a.get("href","").lower() or "content" in a.get("href","").lower()):
                has_skip_link = True
                break

        target_selectors = soup.find_all(["a","button","label","p","span"])
        for el in target_selectors[:150]:  # sample
            style = (el.get("style") or "").lower()
            fg = None; bg = None
            mfg = re.search(r"color\s*:\s*([^;]+)", style)
            mbg = re.search(r"background(?:-color)?\s*:\s*([^;]+)", style)
            if mfg: fg = _parse_css_color(mfg.group(1).strip())
            if mbg: bg = _parse_css_color(mbg.group(1).strip())
            if fg or bg:
                if not fg: fg = (0,0,0)
                if not bg: bg = (1,1,1)
                ratio = contrast_ratio(fg, bg)
                contrast_total += 1
                if ratio < 4.5:  # WCAG AA normal text
                    contrast_fail += 1
            if "outline:" in style and "none" in style:
                outline_none_count += 1

        # keyboard/focus heuristic: interactive but not keyboard friendly (no href, no role, no tabindex)
        for el in soup.find_all(["a","button"], limit=200):
            if el.name == "a" and not el.get("href"):
                focus_issues += 1
            if el.name == "button" and el.get("tabindex") == "-1":
                focus_issues += 1

        contrast_fail_pct = round((contrast_fail / max(1, contrast_total)) * 100.0, 1) if contrast_total else 0.0

        # Internal links sampling for broken
        root = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        internal = []
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if href and not href.startswith(("mailto:", "tel:", "javascript:", "#")):
                abs_url = urljoin(root, href)
                if is_same_domain(root, abs_url):
                    internal.append(abs_url)
        sample = []
        seen = set()
        for l in internal:
            if l in seen: continue
            sample.append(l); seen.add(l)
            if len(sample) >= link_sample: break

        broken = 0; broken_list = []
        for l in sample:
            try:
                rr = requests.head(l, timeout=6, headers=REQ_HEADERS, allow_redirects=True)
                st = rr.status_code
                if st >= 400:
                    rr2 = fetch(l)
                    st = rr2.status_code
                if st >= 400:
                    broken += 1
                    broken_list.append(l)
            except Exception:
                broken += 1
                broken_list.append(l)

        # robots/sitemap
        robots_present, sitemap_declared = False, False
        try:
            rob = requests.get(robots_url(url), timeout=6, headers=REQ_HEADERS)
            if rob.status_code == 200:
                robots_present = True
                sitemap_declared = ("sitemap:" in rob.text.lower())
        except Exception:
            pass

        # Security headers
        hl = {k.lower(): v for k, v in r.headers.items()}
        https_tls = url.lower().startswith("https")
        has_hsts = "strict-transport-security" in hl
        has_csp = "content-security-policy" in hl
        has_xfo = "x-frame-options" in hl
        has_xss = "x-xss-protection" in hl

        # Asset counts
        script_count = len(soup.find_all("script"))
        css_count = len(soup.find_all("link", attrs={"rel": "stylesheet"}))
        img_count = len(imgs)

        # Simple derived scores (bounded)
        def clamp(v): return max(0.0, min(100.0, v))

        perf = 100.0
        perf -= 10 if not compressed else 0
        perf -= 5 if cdn == "Unknown" else 0
        perf -= 10 if size_mb > 3 else (5 if size_mb > 1.5 else 0)
        perf -= 10 if ttfb_ms > 800 else (5 if ttfb_ms > 400 else 0)
        perf = clamp(perf)

        seo = 100.0
        if not title: seo -= 25
        if meta_desc_present != "Yes": seo -= 20
        if h1 != 1: seo -= 10
        if not robots_present: seo -= 10
        if not sitemap_declared: seo -= 5
        if broken > 0: seo -= min(25, broken * 3)
        if not canonical_url: seo -= 5
        if soup.find("meta", attrs={"name": "robots", "content": re.compile("noindex|nofollow", re.I)}):
            seo -= 10
        if not soup.find("link", rel=lambda x: x and "alternate" in x):
            seo -= 0  # no penalty; informational
        if not soup.find("script", attrs={"type": "application/ld+json"}):
            seo -= 5
        seo = clamp(seo)

        acc = 100.0
        if img_count > 0 and alt_cov < 80: acc -= 25
        if aria_missing > 10: acc -= 15
        if contrast_fail_pct > 20: acc -= 15
        if outline_none_count > 0: acc -= 5
        acc = clamp(acc)

        ux = 100.0
        if not has_viewport: ux -= 30
        if broken > 0: ux -= min(20, broken * 2)
        if focus_issues > 0: ux -= min(20, focus_issues * 2)
        ux = clamp(ux)

        sec = 100.0
        if not https_tls: sec -= 40
        if https_tls and not has_hsts: sec -= 10
        if not has_csp: sec -= 20
        if not has_xfo: sec -= 10
        if not has_xss: sec -= 5
        sec = clamp(sec)

        out.update({
            "ok": True,
            "url": url,
            "domain": urlparse(url).netloc,
            "timestamp": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "ttfb_ms": round(ttfb_ms, 1),
            "size_mb": size_mb,
            "compressed": "Yes" if compressed else "No",
            "cdn": cdn,
            "content_type": content_type,
            "title": title,
            "meta_desc": meta_desc_present,
            "canonical_url": canonical_url,
            "viewport": "Yes" if has_viewport else "No",
            "h1": h1, "h2": h2, "h3": h3,
            "img_count": img_count,
            "alt_coverage": alt_cov,
            "aria_missing": aria_missing,
            "contrast_fail_pct": contrast_fail_pct,
            "outline_none_count": outline_none_count,
            "skip_link": "Yes" if has_skip_link else "No",
            "schema": "Yes" if soup.find("script", attrs={"type": "application/ld+json"}) else "No",
            "robots": "Yes" if robots_present else "No",
            "sitemap": "Yes" if sitemap_declared else "No",
            "scripts": script_count,
            "stylesheets": css_count,
            "internal_links_sampled": len(sample),
            "broken_links": broken,
            "broken_list": broken_list[:40],
            "security_headers": {
                "https_tls": "Yes" if https_tls else "No",
                "hsts": "Yes" if has_hsts else "No",
                "csp": "Yes" if has_csp else "No",
                "x_frame_options": "Yes" if has_xfo else "No",
                "x_xss_protection": "Yes" if has_xss else "No",
            },
            "scores": {
                "performance": perf,
                "seo": seo,
                "accessibility": acc,
                "ux": ux,
                "security": sec,
            }
        })
    except Exception as e:
        out["ok"] = False
        out["error"] = str(e)
    return out

# Optional: PageSpeed (Lighthouse-like) highlights
def pagespeed_highlights(url: str, api_key: Optional[str]) -> Dict[str, Any]:
    if not api_key:
        return {}
    try:
        endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {"url": url, "strategy": "desktop", "key": api_key}
        data = requests.get(endpoint, params=params, timeout=20).json()
        cats = data.get("lighthouseResult", {}).get("categories", {}) or {}
        audits = data.get("lighthouseResult", {}).get("audits", {}) or {}
        lcp = audits.get("largest-contentful-paint", {}).get("numericValue")
        cls = audits.get("cumulative-layout-shift", {}).get("numericValue")
        inp = audits.get("interactive", {}).get("numericValue")
        return {
            "ps_performance": (cats.get("performance", {}).get("score", 0) or 0) * 100,
            "ps_seo": (cats.get("seo", {}).get("score", 0) or 0) * 100,
            "ps_accessibility": (cats.get("accessibility", {}).get("score", 0) or 0) * 100,
            "lcp_ms": float(lcp) if lcp is not None else None,
            "cls": float(cls) if cls is not None else None,
            "inp_ms": float(inp) if inp is not None else None,
        }
    except Exception:
        return {}

# =========================================
# GA / GSC INGESTION (dict or CSV paths)
# =========================================
def read_csv_kv_pairs(path: str) -> Dict[str, float]:
    data = {}
    with open(path, "r", newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or len(row) < 2: continue
            key = str(row[0]).strip()
            try:
                val = float(row[1])
            except:
                val = row[1]
            data[key] = val
    return data

def ingest_ga(ga: Optional[Dict[str, Any]] = None,
              trend_csv: Optional[str] = None,
              sources_csv: Optional[str] = None) -> Dict[str, Any]:
    """
    Return dict with:
      trend: list[[label, value], ...]
      sources: {channel: value}
      metrics: total_visitors, organic, direct, referral, social, paid, bounce_rate, avg_session_duration, pages_per_session
    """
    out = {"trend": [], "sources": {}, "metrics": {}}
    if ga:
        out["trend"] = ga.get("trend", [])
        out["sources"] = ga.get("sources", {})
        out["metrics"] = {**ga}
        for k in ["trend","sources"]:
            out["metrics"].pop(k, None)
    if trend_csv and os.path.exists(trend_csv):
        arr = []
        with open(trend_csv, "r", newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    try:
                        arr.append([row[0], float(row[1])])
                    except:
                        pass
        if arr: out["trend"] = arr
    if sources_csv and os.path.exists(sources_csv):
        out["sources"] = read_csv_kv_pairs(sources_csv)
    return out

def ingest_gsc(gsc: Optional[Dict[str, Any]] = None,
               queries_csv: Optional[str] = None) -> Dict[str, Any]:
    """
    Return dict with:
      impressions, clicks, ctr
      queries: list of {query, clicks}
    """
    out = {"impressions": None, "clicks": None, "ctr": None, "queries": []}
    if gsc:
        out.update({k: gsc.get(k) for k in ["impressions","clicks","ctr"]})
        out["queries"] = gsc.get("queries", [])
    if queries_csv and os.path.exists(queries_csv):
        arr = []
        with open(queries_csv, "r", newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    try:
                        arr.append({"query": row[0], "clicks": float(row[1])})
                    except:
                        pass
        if arr: out["queries"] = arr
    return out

# =========================================
# COMPETITORS INGESTION
# =========================================
def ingest_competitors(comps: Optional[List[Dict[str, Any]]] = None,
                       csv_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    competitor: {
        name/domain, performance, security, seo, accessibility, ux,
        traffic_trend: [[label, value], ...]
    }
    """
    out = []
    if comps:
        out = comps
    if csv_path and os.path.exists(csv_path):
        # CSV: name,performance,security,seo,accessibility,ux,trend_json
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                c = {
                    "name": row.get("name") or row.get("domain") or "Competitor",
                    "performance": float(row.get("performance", 0) or 0),
                    "security": float(row.get("security", 0) or 0),
                    "seo": float(row.get("seo", 0) or 0),
                    "accessibility": float(row.get("accessibility", 0) or 0),
                    "ux": float(row.get("ux", 0) or 0),
                    "traffic_trend": []
                }
                t = row.get("trend_json")
                if t:
                    try: c["traffic_trend"] = json.loads(t)
                    except: pass
                out.append(c)
    return out[:8]

# =========================================
# SCORING / STATUS
# =========================================
def weighted_overall(scores: Dict[str, float]) -> float:
    s = 0.0
    for k, w in WEIGHTAGE.items():
        s += float(scores.get(k, 0)) * w
    return round(s, 2)

def status_from_score(v: float) -> str:
    if v >= 85: return "Good"
    if v >= 65: return "Warning"
    return "Critical"

# =========================================
# CHARTS
# =========================================
def _fig_to_buf() -> io.BytesIO:
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150)
    plt.close()
    buf.seek(0)
    return buf

def bar_chart(items: List[Tuple[str, float]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    if not items: return empty_chart("No data")
    labels = [i[0] for i in items]
    values = [float(i[1]) for i in items]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.bar(labels, values, color="#2E86DE")
    ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3); plt.xticks(rotation=25, ha="right")
    return _fig_to_buf()

def line_chart(points: List[Tuple[str, float]], title: str, xlabel: str = "", ylabel: str = "") -> io.BytesIO:
    if not points: return empty_chart("No data")
    labels = [p[0] for p in points]
    values = [float(p[1]) for p in points]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.plot(labels, values, marker="o", color="#0F62FE")
    ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3); plt.xticks(rotation=25, ha="right")
    return _fig_to_buf()

def multi_line_chart(series: Dict[str, List[Tuple[str, float]]], title: str, xlabel: str, ylabel: str) -> io.BytesIO:
    if not series: return empty_chart("No data")
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    for name, pts in series.items():
        labels = [p[0] for p in pts]
        values = [float(p[1]) for p in pts]
        ax.plot(labels, values, marker="o", linewidth=2, label=name)
    ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3); plt.xticks(rotation=25, ha="right")
    ax.legend()
    return _fig_to_buf()

def pie_chart(parts: List[Tuple[str, float]], title: str = "") -> io.BytesIO:
    if not parts: return empty_chart("No data")
    labels = [p[0] for p in parts]
    sizes = [max(0.0, float(p[1])) for p in parts]
    if sum(sizes) <= 0: sizes = [1.0 for _ in sizes]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140)
    ax.axis("equal"); ax.set_title(title)
    return _fig_to_buf()

def radar_chart(categories: List[str], values: List[float], title: str = "") -> io.BytesIO:
    if not categories or not values: return empty_chart("No data")
    N = len(categories)
    vals = [float(v) for v in values[:N]]
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    vals += vals[:1]; angles += angles[:1]
    fig = plt.figure(figsize=(5.6, 5.0))
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi/2); ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), categories)
    ax.set_ylim(0, 100)
    ax.plot(angles, vals, color="#2F80ED", linewidth=2)
    ax.fill(angles, vals, color="#2F80ED", alpha=0.2)
    ax.set_title(title, y=1.1)
    return _fig_to_buf()

def empty_chart(msg: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.axis("off"); ax.text(0.5, 0.5, msg, ha="center", va="center")
    return _fig_to_buf()

# =========================================
# TABLE HELPERS
# =========================================
def kpi_table(rows: List[Dict[str, Any]], show_status_color: bool = True) -> Table:
    headers = ["KPI", "Value", "Status"]
    data = [headers]
    for r in rows:
        data.append([str(r.get("name","")), str(r.get("value","")), str(r.get("status",""))])

    t = Table(data, colWidths=[3.1*inch, 1.1*inch, 1.1*inch], repeatRows=1)
    styles = [
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, GRID),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]
    if show_status_color:
        for i in range(1, len(data)):
            status = (data[i][2] or "").lower()
            color = BAD_COLOR
            if status.startswith("good"): color = OK_COLOR
            elif status.startswith("warn"): color = WARN_COLOR
            styles.append(("TEXTCOLOR", (2,i), (2,i), color))
    t.setStyle(TableStyle(styles))
    return t

# =========================================
# RECOMMENDATIONS ENGINE (SIMPLE)
# =========================================
def recommendations(live: Dict[str, Any]) -> List[str]:
    recs: List[str] = []
    def add(x):
        if x not in recs: recs.append(x)

    if live.get("meta_desc") != "Yes" or not live.get("title"):
        add("Add or improve <title> and meta description for better relevance and CTR.")
    if live.get("h1", 0) != 1:
        add("Ensure exactly one descriptive H1 per page; organize H2/H3 for structure.")
    if live.get("broken_links", 0) > 0:
        add("Fix broken internal links to improve crawlability and UX.")
    if live.get("schema") != "Yes":
        add("Implement structured data (Schema.org) for key templates.")
    if live.get("compressed") != "Yes":
        add("Enable Brotli/Gzip and HTTP/2/3; ensure server-side compression.")
    if (live.get("security_headers", {}).get("hsts") != "Yes") or (live.get("security_headers", {}).get("https_tls") != "Yes"):
        add("Enforce HTTPS with HSTS to prevent downgrade/SSL stripping.")
    if live.get("security_headers", {}).get("csp") != "Yes":
        add("Set a strict Content-Security-Policy to mitigate XSS.")
    if live.get("alt_coverage", 100) < 80 or live.get("aria_missing", 0) > 10:
        add("Improve alt text coverage and ARIA attributes; test with screen readers.")
    if live.get("viewport") != "Yes":
        add("Add responsive viewport meta for mobile users.")
    if live.get("contrast_fail_pct", 0) > 20:
        add("Improve color contrast to meet WCAG AA (contrast ratio ≥ 4.5:1).")
    if live.get("outline_none_count", 0) > 0:
        add("Avoid disabling focus outlines; ensure clear keyboard focus styles.")
    if live.get("skip_link") != "Yes":
        add("Add a 'Skip to content' link for better keyboard navigation.")
    return recs[:15]

# =========================================
# PDF BUILDER
# =========================================
def _score_items(scores: Dict[str, float]) -> List[Tuple[str, float]]:
    return [(k.capitalize(), float(scores.get(k, 0))) for k in ["performance","security","seo","accessibility","ux"]]

def generate_audit_pdf(
    url: str,
    output_path: Optional[str] = None,
    dashboard_url: Optional[str] = None,
    pagespeed_api_key: Optional[str] = None,
    ga: Optional[Dict[str, Any]] = None,
    gsc: Optional[Dict[str, Any]] = None,
    competitors: Optional[List[Dict[str, Any]]] = None,
    ga_trend_csv: Optional[str] = None,
    ga_sources_csv: Optional[str] = None,
    gsc_queries_csv: Optional[str] = None,
    competitors_csv: Optional[str] = None,
    history: Optional[Dict[str, List[Tuple[str, float]]]] = None
) -> bytes:

    live = audit_site(url)
    ps   = pagespeed_highlights(url, pagespeed_api_key) if pagespeed_api_key else {}
    scores = live.get("scores", {}) if live.get("ok") else {}
    overall = weighted_overall(scores) if scores else 0.0

    # Ingest external data
    ga_data  = ingest_ga(ga, trend_csv=ga_trend_csv, sources_csv=ga_sources_csv)
    gsc_data = ingest_gsc(gsc, queries_csv=gsc_queries_csv)
    comp_data= ingest_competitors(competitors, csv_path=competitors_csv)
    history  = history or {}

    buf = io.BytesIO()
    doc = TOCDoc(
        buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=54, bottomMargin=54,
        title=f"{COMPANY} Web Audit", author=COMPANY
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Caption", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6F6F6F")))
    styles.add(ParagraphStyle(name="KPIHeader", parent=styles["Heading2"], textColor=PRIMARY))
    elements: List[Any] = []

    # 1) COVER PAGE
    elements.append(P(COMPANY, styles["Title"]))
    elements.append(Spacer(1, 0.12*inch))
    elements.append(P("Web Audit Report", styles["Heading1"]))
    elements.append(Spacer(1, 0.06*inch))
    elements.append(P(f"Website: {url}", styles["Normal"]))
    elements.append(P(f"Domain: {urlparse(url).netloc}", styles["Normal"]))
    elements.append(P(f"Report Time (UTC): {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
    elements.append(P(f"Audit/Tool Version: {VERSION}", styles["Normal"]))
    elements.append(Spacer(1, 0.12*inch))
    if dashboard_url or url:
        try:
            code = qr.QrCodeWidget(dashboard_url or url)
            bx = code.getBounds()
            w = bx[2]-bx[0]; h = bx[3]-bx[1]
            d = Drawing(1.4*inch, 1.4*inch, transform=[1.4*inch / w, 0, 0, 1.4*inch / h, 0, 0])
            d.add(code)
            elements.append(d)
            elements.append(P("Scan to view online dashboard", styles["Caption"]))
        except Exception:
            pass
    elements.append(PageBreak())

    # 3) TABLE OF CONTENTS
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(fontName="Helvetica-Bold", name="TOCHeading1", fontSize=12, leftIndent=20, firstLineIndent=-10, spaceBefore=6),
        ParagraphStyle(fontName="Helvetica", name="TOCHeading2", fontSize=10, leftIndent=36, firstLineIndent=-10, spaceBefore=2),
    ]
    elements.append(P("Table of Contents", styles["Heading1"]))
    elements.append(Spacer(1, 0.08*inch))
    elements.append(toc)
    elements.append(PageBreak())

    # 2) EXECUTIVE SUMMARY
    elements.append(P("Executive Summary", styles["Heading1"]))
    elements.append(Spacer(1, 0.06*inch))
    elements.append(P(f"Overall Website Health Score: {overall}/100", styles["Heading2"]))

    # Category table
    cat_rows = [["Category", "Score", "Status"]]
    for k in ["performance","security","seo","accessibility","ux"]:
        sc = float(scores.get(k, 0))
        cat_rows.append([k.capitalize(), f"{sc:.0f}", status_from_score(sc)])
    cat_table = Table(cat_rows, colWidths=[3.1*inch, 1.0*inch, 1.1*inch], repeatRows=1)
    cat_style = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, GRID),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
    ])
    for i in range(1, len(cat_rows)):
        st = (cat_rows[i][2] or "").lower()
        color = BAD_COLOR
        if st.startswith("good"): color = OK_COLOR
        elif st.startswith("warn"): color = WARN_COLOR
        cat_style.add("TEXTCOLOR", (2,i), (2,i), color)
    cat_table.setStyle(cat_style)
    elements.append(cat_table)

    # Highlights (from live)
    if live.get("ok"):
        elements.append(Spacer(1, 0.10*inch))
        hi_rows = [
            ["TTFB (ms)", str(live.get("ttfb_ms"))],
            ["Page Weight (MB)", str(live.get("size_mb"))],
            ["Compression", live.get("compressed", "No")],
            ["CDN", live.get("cdn", "Unknown")],
            ["robots.txt", live.get("robots", "No")],
            ["Sitemap Declared", live.get("sitemap", "No")],
            ["Broken Links (sample)", f"{live.get('broken_links',0)}/{live.get('internal_links_sampled',0)}"],
        ]
        mini = Table([["Highlight","Value"]] + hi_rows, colWidths=[2.6*inch, 2.0*inch], repeatRows=1)
        mini.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
            ("GRID", (0,0), (-1,-1), 0.25, GRID),
            ("FONTSIZE", (0,0), (-1,-1), 9),
        ]))
        elements.append(mini)

    elements.append(Image(bar_chart(_score_items(scores), "Category Scores", "Category", "Score"), width=5.8*inch, height=3.2*inch))

    if pagespeed_api_key:
        vitals = []
        if ps.get("lcp_ms") is not None: vitals.append(("LCP (ms)", ps["lcp_ms"]))
        if ps.get("inp_ms") is not None: vitals.append(("INP/Interactive (ms)", ps["inp_ms"]))
        if ps.get("cls") is not None: vitals.append(("CLS (x1000)", (ps["cls"] or 0)*1000))
        elements.append(Image(bar_chart(vitals, "Core Web Vitals (PSI)", "Metric", "Value"), width=5.8*inch, height=3.2*inch))
    else:
        elements.append(Image(empty_chart("No PageSpeed API key provided"), width=5.8*inch, height=3.2*inch))

    # Recommendations
    elements.append(Spacer(1, 0.12*inch))
    elements.append(P("Top Recommendations", styles["KPIHeader"]))
    for rec in recommendations(live):
        elements.append(P(rec, styles["Normal"], bullet="•"))
    elements.append(PageBreak())

    # 4) PERFORMANCE
    elements.append(P("Performance KPIs", styles["Heading1"]))
    perf_rows = [
        {"name":"Time To First Byte (ms)", "value": live.get("ttfb_ms","N/A"), "status": "Good" if isinstance(live.get("ttfb_ms"),(int,float)) and live.get("ttfb_ms")<=800 else "Warning"},
        {"name":"Page Weight (MB)", "value": live.get("size_mb","N/A"), "status": "Good" if isinstance(live.get("size_mb"),(int,float)) and live.get("size_mb")<=3 else "Warning"},
        {"name":"Compression (gzip/brotli)", "value": live.get("compressed","No"), "status": "Good" if live.get("compressed")=="Yes" else "Warning"},
        {"name":"CDN Detected", "value": live.get("cdn","Unknown"), "status": "Good" if live.get("cdn","Unknown")!="Unknown" else "Warning"},
        {"name":"Scripts (count)", "value": live.get("scripts",0), "status": "Good" if live.get("scripts",0)<=60 else "Warning"},
        {"name":"Stylesheets (count)", "value": live.get("stylesheets",0), "status": "Good" if live.get("stylesheets",0)<=15 else "Warning"},
        {"name":"Images (count)", "value": live.get("img_count",0), "status": "Good" if live.get("img_count",0)<=120 else "Warning"},
        {"name":"Viewport (mobile)", "value": live.get("viewport","No"), "status": "Good" if live.get("viewport")=="Yes" else "Warning"},
    ]
    elements.append(kpi_table(perf_rows))
    elements.append(Image(bar_chart([(r["name"][:18], 100 if r["status"]=="Good" else (60 if r["status"]=="Warning" else 20)) for r in perf_rows], "Performance Snapshot", "KPI", "Score"), width=5.8*inch, height=3.2*inch))
    elements.append(PageBreak())

    # 5) SEO
    elements.append(P("SEO KPIs", styles["Heading1"]))
    seo_rows = [
        {"name":"Title Tag Present", "value": "Yes" if live.get("title") else "No", "status": "Good" if live.get("title") else "Critical"},
        {"name":"Meta Description Present", "value": live.get("meta_desc","No"), "status": "Good" if live.get("meta_desc")=="Yes" else "Warning"},
        {"name":"Canonical Tag Present", "value": "Yes" if live.get("canonical_url") else "No", "status": "Good" if live.get("canonical_url") else "Warning"},
        {"name":"H1 Count", "value": live.get("h1",0), "status": "Good" if live.get("h1",0)==1 else "Warning"},
        {"name":"H2 Count", "value": live.get("h2",0), "status": "Good" if live.get("h2",0)>=1 else "Warning"},
        {"name":"H3 Count", "value": live.get("h3",0), "status": "Good" if live.get("h3",0)>=1 else "Warning"},
        {"name":"robots.txt Present", "value": live.get("robots","No"), "status": "Good" if live.get("robots")=="Yes" else "Warning"},
        {"name":"Sitemap Declared", "value": live.get("sitemap","No"), "status": "Good" if live.get("sitemap")=="Yes" else "Warning"},
        {"name":"Broken Links (sample)", "value": live.get("broken_links",0), "status": "Good" if live.get("broken_links",0)==0 else "Warning"},
        {"name":"Image Alt Coverage (%)", "value": live.get("alt_coverage",0), "status": "Good" if live.get("alt_coverage",0)>=80 else "Warning"},
        {"name":"Structured Data (Schema.org)", "value": live.get("schema","No"), "status": "Good" if live.get("schema")=="Yes" else "Warning"},
    ]
    elements.append(kpi_table(seo_rows))
    elements.append(Image(bar_chart([(r["name"][:20], 100 if r["status"]=="Good" else (60 if r["status"]=="Warning" else 20)) for r in seo_rows], "SEO Snapshot", "KPI", "Score"), width=5.8*inch, height=3.2*inch))
    elements.append(PageBreak())

    # 6) SECURITY
    elements.append(P("Security KPIs", styles["Heading1"]))
    sh = live.get("security_headers", {})
    sec_rows = [
        {"name":"HTTPS / TLS", "value": sh.get("https_tls","No"), "status": "Good" if sh.get("https_tls")=="Yes" else "Critical"},
        {"name":"HSTS Header", "value": sh.get("hsts","No"), "status": "Good" if sh.get("hsts")=="Yes" else "Warning"},
        {"name":"Content-Security-Policy", "value": sh.get("csp","No"), "status": "Good" if sh.get("csp")=="Yes" else "Warning"},
        {"name":"X-Frame-Options", "value": sh.get("x_frame_options","No"), "status": "Good" if sh.get("x_frame_options")=="Yes" else "Warning"},
        {"name":"X-XSS-Protection", "value": sh.get("x_xss_protection","No"), "status": "Good" if sh.get("x_xss_protection")=="Yes" else "Warning"},
        {"name":"Broken Links (proxy risk)", "value": live.get("broken_links",0), "status": "Good" if live.get("broken_links",0)==0 else "Warning"},
    ]
    elements.append(kpi_table(sec_rows))
    elements.append(Image(bar_chart([(r["name"][:20], 100 if r["status"]=="Good" else (60 if r["status"]=="Warning" else 20)) for r in sec_rows], "Security Snapshot", "KPI", "Score"), width=5.8*inch, height=3.2*inch))
    elements.append(PageBreak())

    # 7) ACCESSIBILITY (A11y)
    elements.append(P("Accessibility KPIs", styles["Heading1"]))
    acc_rows = [
        {"name":"Alt Text Coverage (%)", "value": live.get("alt_coverage",0), "status": "Good" if live.get("alt_coverage",0)>=80 else "Warning"},
        {"name":"ARIA Missing (count)", "value": live.get("aria_missing",0), "status": "Good" if live.get("aria_missing",0)<=10 else "Warning"},
        {"name":"Viewport (mobile)", "value": live.get("viewport","No"), "status": "Good" if live.get("viewport")=="Yes" else "Warning"},
        {"name":"Headings Structure (H1)", "value": live.get("h1",0), "status": "Good" if live.get("h1",0)==1 else "Warning"},
        {"name":"Contrast Failures (%)", "value": live.get("contrast_fail_pct",0), "status": "Good" if live.get("contrast_fail_pct",0)<=20 else "Warning"},
        {"name":"Focus Outline Disabled (count)", "value": live.get("outline_none_count",0), "status": "Good" if live.get("outline_none_count",0)==0 else "Warning"},
        {"name":"'Skip to content' Link", "value": live.get("skip_link","No"), "status": "Good" if live.get("skip_link")=="Yes" else "Warning"},
    ]
    elements.append(kpi_table(acc_rows))
    a11y_radar = radar_chart(
        ["Alt Coverage","ARIA","Structure(H1)","Viewport","Contrast","Focus"],
        [
            live.get("alt_coverage",0),
            max(0.0, 100.0 - min(100.0, live.get("aria_missing",0)*5.0)),
            100.0 if live.get("h1",0)==1 else 70.0,
            100.0 if live.get("viewport")=="Yes" else 40.0,
            max(0.0, 100.0 - min(100.0, live.get("contrast_fail_pct",0))),
            max(0.0, 100.0 - min(100.0, live.get("outline_none_count",0)*10.0))
        ], "Accessibility Radar"
    )
    elements.append(Image(a11y_radar, width=5.2*inch, height=4.8*inch))
    elements.append(PageBreak())

    # 8) USER EXPERIENCE (UX)
    elements.append(P("UX KPIs", styles["Heading1"]))
    ux_rows = [
        {"name":"Mobile-Friendliness (Viewport)", "value": live.get("viewport","No"), "status": "Good" if live.get("viewport")=="Yes" else "Warning"},
        {"name":"Broken Links (count)", "value": live.get("broken_links",0), "status": "Good" if live.get("broken_links",0)==0 else "Warning"},
        {"name":"Page Weight (MB)", "value": live.get("size_mb",0), "status": "Good" if live.get("size_mb",0)<=3 else "Warning"},
        {"name":"Keyboard Focus Issues (proxy)", "value": f"{max(0, 100 - min(100, live.get('outline_none_count',0)*5))} score", "status": "Good" if live.get("outline_none_count",0)==0 else "Warning"},
    ]
    elements.append(kpi_table(ux_rows))
    ux_radar = radar_chart(
        ["Mobile","Broken Links","Readability*","Interactivity*"],
        [
            100.0 if live.get("viewport")=="Yes" else 40.0,
            max(0.0, 100.0 - min(100.0, live.get("broken_links",0)*8.0)),
            70.0, 70.0
        ], "UX Radar (*proxy)"
    )
    elements.append(Image(ux_radar, width=5.2*inch, height=4.8*inch))
    elements.append(PageBreak())

    # 9) TRAFFIC & ANALYTICS (GA/GA4 + GSC)
    elements.append(P("Traffic & Analytics", styles["Heading1"]))
    # GA Trend
    if ga_data.get("trend"):
        elements.append(Image(line_chart([(str(p[0]), float(p[1])) for p in ga_data["trend"]], "Traffic Trend", "Period", "Visits"), width=5.8*inch, height=3.2*inch))
    else:
        elements.append(Image(empty_chart("No GA trend provided"), width=5.8*inch, height=3.2*inch))
    # GA Sources
    if ga_data.get("sources"):
        parts = [(k, float(v)) for k, v in ga_data["sources"].items()]
        elements.append(Image(pie_chart(parts, "Traffic Sources"), width=4.8*inch, height=4.8*inch))
    else:
        elements.append(Image(empty_chart("No GA sources provided"), width=5.8*inch, height=3.2*inch))
    # GA Metrics mini-table
    if ga_data.get("metrics"):
        kv = ga_data["metrics"]
        rows = []
        for k in ["total_visitors","organic","direct","referral","social","paid","bounce_rate","avg_session_duration","pages_per_session"]:
            if k in kv:
                rows.append([k.replace("_"," ").title(), str(kv.get(k))])
        if rows:
            t = Table([["GA Metric","Value"]] + rows, colWidths=[2.6*inch, 2.0*inch], repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
                ("GRID", (0,0), (-1,-1), 0.25, GRID),
                ("FONTSIZE", (0,0), (-1,-1), 9),
            ]))
            elements.append(t)
    # GSC summary
    if gsc_data:
        rows = []
        for k in ["impressions","clicks","ctr"]:
            rows.append([k.upper(), str(gsc_data.get(k))])
        t = Table([["GSC Metric","Value"]] + rows, colWidths=[2.6*inch, 2.0*inch], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
            ("GRID", (0,0), (-1,-1), 0.25, GRID),
            ("FONTSIZE", (0,0), (-1,-1), 9),
        ]))
        elements.append(t)
        if gsc_data.get("queries"):
            top_q = gsc_data["queries"][:10]
            items = [(str(q.get("query",""))[:24], float(q.get("clicks",0))) for q in top_q]
            elements.append(Image(bar_chart(items, "Top Queries by Clicks", "Query", "Clicks"), width=5.8*inch, height=3.2*inch))
        else:
            elements.append(Image(empty_chart("No GSC queries provided"), width=5.8*inch, height=3.2*inch))
    elements.append(PageBreak())

    # 10) BENCHMARKING & COMPETITORS
    elements.append(P("Benchmarking & Competitor Comparison", styles["Heading1"]))
    if comp_data:
        series = {}
        for comp in comp_data[:6]:
            name = comp.get("name") or comp.get("domain") or "Competitor"
            trend = comp.get("traffic_trend") or []
            if trend:
                series[name] = [(str(p[0]), float(p[1])) for p in trend][:12]
        if series:
            elements.append(Image(multi_line_chart(series, "Traffic vs Competitors", "Period", "Traffic"), width=6.2*inch, height=3.6*inch))
        score_bars = []
        for c in comp_data[:6]:
            nm = str(c.get("name") or c.get("domain") or "Comp")[:18]
            score_bars.append((f"{nm}-SEO", float(c.get("seo",0))))
        if score_bars:
            elements.append(Image(bar_chart(score_bars, "Competitor SEO Scores", "Competitor", "Score"), width=6.2*inch, height=3.6*inch))
    else:
        elements.append(Image(empty_chart("No competitor data provided"), width=5.8*inch, height=3.2*inch))
    elements.append(PageBreak())

    # 11) GRAPHICAL CHARTS (Summary)
    elements.append(P("Graphical Charts (Summary)", styles["Heading1"]))
    elements.append(Image(bar_chart(_score_items(scores), "Category Scores", "Category", "Score"), width=5.8*inch, height=3.2*inch))
    elements.append(Image(radar_chart(["Perf","Sec","SEO","A11y","UX"], [scores.get("performance",0), scores.get("security",0), scores.get("seo",0), scores.get("accessibility",0), scores.get("ux",0)], "Overall Radar"), width=5.2*inch, height=4.8*inch))
    # History trends (optional)
    added = False
    for key, label, ylabel in [
        ("traffic","Traffic Trend","Traffic"),
        ("keyword_rank","Keyword Ranking Trend","Avg Rank"),
        ("page_speed","Page Speed Trend (ms)","ms"),
        ("sec_vulns","Security Vulnerabilities Trend","Count"),
        ("engagement","Engagement Trend (Pages/Session)","Pages/Session"),
    ]:
        if key in history and history[key]:
            pts = [(str(p[0]), float(p[1])) for p in history[key]][:12]
            elements.append(Image(line_chart(pts, label, "Period", ylabel), width=5.8*inch, height=3.2*inch))
            added = True
    if not added:
        elements.append(Image(empty_chart("No historical series provided"), width=5.8*inch, height=3.2*inch))
    elements.append(PageBreak())

    # 12) RECOMMENDATIONS / ACTION PLAN
    elements.append(P("Recommendations / Action Plan", styles["Heading1"]))
    recs = recommendations(live)
    if recs:
        for rec in recs:
            elements.append(P(rec, styles["Normal"], bullet="•"))
    else:
        elements.append(P("No recommendations generated.", styles["Normal"]))
    elements.append(Image(empty_chart("End of recommendations"), width=5.8*inch, height=3.2*inch))
    elements.append(PageBreak())

    # 13) DIGITAL CERTIFICATION PAGE
    elements.append(P("Certificate of Audit", styles["Heading1"]))
    payload = json.dumps({"live": live, "scores": scores, "generated_at": dt.datetime.utcnow().isoformat()}, sort_keys=True).encode("utf-8")
    signature = hashlib.sha256(payload).hexdigest()
    elements.append(P(f"This certifies that an automated web audit was conducted on {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.", styles["Normal"]))
    elements.append(P(f"Digital Signature (SHA-256): {signature}", styles["Normal"]))
    elements.append(Image(empty_chart("Digital Certification Visual"), width=5.8*inch, height=3.2*inch))
    elements.append(PageBreak())

    # 14) APPENDICES / RAW DATA (Excerpt + Broken Links)
    elements.append(P("Appendices / Raw Data (Excerpt)", styles["Heading1"]))
    fields = [
        ("URL", live.get("url","")),
        ("Domain", live.get("domain","")),
        ("Content-Type", live.get("content_type","")),
        ("Scripts", live.get("scripts",0)),
        ("Stylesheets", live.get("stylesheets",0)),
        ("Images", live.get("img_count",0)),
        ("Alt Coverage (%)", live.get("alt_coverage",0)),
        ("ARIA Missing", live.get("aria_missing",0)),
        ("Contrast Fails (%)", live.get("contrast_fail_pct",0)),
        ("Focus Outline Disabled", live.get("outline_none_count",0)),
        ("Skip Link Present", live.get("skip_link","No")),
        ("robots.txt", live.get("robots","No")),
        ("Sitemap", live.get("sitemap","No")),
        ("CDN", live.get("cdn","Unknown")),
    ]
    appendix_tbl = Table([["Field","Value"]] + [[k, str(v)] for k,v in fields], colWidths=[2.6*inch, 2.8*inch], repeatRows=1)
    appendix_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F8")),
        ("GRID", (0,0), (-1,-1), 0.25, GRID),
        ("FONTSIZE", (0,0), (-1,-1), 9),
    ]))
    elements.append(appendix_tbl)

    if live.get("broken_list"):
        elements.append(Spacer(1, 0.12*inch))
        elements.append(P("Broken Links (sample)", styles["KPIHeader"]))
        for lnk in live["broken_list"]:
            elements.append(P(f"• {lnk}", styles["Normal"]))

    # Build
    def _first(c,d): draw_header_footer(c,d,url)
    def _later(c,d): draw_header_footer(c,d,url)
    doc.build(elements, onFirstPage=_first, onLaterPages=_later)

    pdf_bytes = buf.getvalue()
    buf.close()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    return pdf_bytes

# =========================================
# CLI
# =========================================
def main():
    parser = argparse.ArgumentParser(description="FF Tech Web Audit PDF Generator (Enterprise, single file)")
    parser.add_argument("--url", required=True, help="Target website URL (e.g., https://www.apple.com)")
    parser.add_argument("--out", default="fftech_web_audit.pdf", help="Output PDF path")
    parser.add_argument("--dashboard", default=None, help="Dashboard/online report URL for QR code (optional)")
    parser.add_argument("--psi-key", default=None, help="Google PageSpeed Insights API key (optional)")
    # GA/GSC/Competitors optional ingestion
    parser.add_argument("--ga-json", default=None, help="Inline GA JSON string or path to GA JSON")
    parser.add_argument("--ga-trend-csv", default=None, help="GA trend CSV path (period, value)")
    parser.add_argument("--ga-sources-csv", default=None, help="GA sources CSV path (channel, value)")
    parser.add_argument("--gsc-json", default=None, help="Inline GSC JSON string or path to GSC JSON")
    parser.add_argument("--gsc-queries-csv", default=None, help="GSC queries CSV path (query, clicks)")
    parser.add_argument("--competitors-json", default=None, help="Inline competitors JSON string or path")
    parser.add_argument("--competitors-csv", default=None, help="Competitors CSV path")
    parser.add_argument("--history-json", default=None, help="Inline history JSON string or path")
    args = parser.parse_args()

    def load_json_maybe(s: Optional[str]):
        if not s: return None
        if os.path.exists(s):
            with open(s, "r", encoding="utf-8") as f: return json.load(f)
        try:
            return json.loads(s)
        except:
            return None

    ga = load_json_maybe(args.ga_json)
    gsc = load_json_maybe(args.gsc_json)
    competitors = load_json_maybe(args.competitors_json)
    history = load_json_maybe(args.history_json)

    pdf = generate_audit_pdf(
        args.url,
        output_path=args.out,
        dashboard_url=args.dashboard,
        pagespeed_api_key=args.psi_key,
        ga=ga,
        gsc=gsc,
        competitors=competitors,
        ga_trend_csv=args.ga_trend_csv,
        ga_sources_csv=args.ga_sources_csv,
        gsc_queries_csv=args.gsc_queries_csv,
        competitors_csv=args.competitors_csv,
        history=history
    )
    print(f"Saved: {args.out}")

if __name__ == "__main__":
    main()
