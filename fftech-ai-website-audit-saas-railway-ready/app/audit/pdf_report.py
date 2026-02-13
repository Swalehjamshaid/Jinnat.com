# -*- coding: utf-8 -*-
"""
FF TECH ENTERPRISE WEBSITE AUDIT SAAS
Filename: pdf_report.py (updated)
Railway-Ready | Single-File Executable | No External Dependencies (except standard libs & common py libs)

What's new in this version
--------------------------
• Expanded audit engine to populate all sections requested by user (SEO, Performance, Security, Accessibility, UX, Links, Tracking)
• Safer network timeouts, graceful fallbacks, and clear N/A markers where lab/field APIs are required
• Executive Summary with radar + bar chart, risk level, top-5 critical issues, and impact estimates
• Cover page with optional company logo, confidentiality notice, and QR to target
• Website overview (domain, IP, SSL, redirects, page size, total requests, etc.)
• Broken link sampler table with internal/external classification
• Clean, printer-friendly PDF layout

Note: This module performs best-effort static checks. Certain metrics (e.g., Core Web Vitals, FCP/LCP/TTI,
PageSpeed API results, precise hosting provider and geo-location) require external APIs or RUM/Lab tools and are
marked as N/A unless you integrate those APIs.
"""

import io
import re
import os
import ssl
import json
import time
import socket
import hashlib
import logging
import datetime as dt
from collections import Counter
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# PDF Rendering
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, ListFlowable, ListItem, KeepTogether
)
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing

# Data Visualization
import matplotlib
matplotlib.use("Agg")  # Headless-safe for server environments
import matplotlib.pyplot as plt
import numpy as np

# =========================================
# BRANDING & SCORING CONFIG
# =========================================
COMPANY = "FF Tech"
SAAS_NAME = "FF Tech Enterprise Website Audit"
VERSION = "v5.0-Enterprise"

WEIGHTS = {
    "performance": 0.30,
    "security": 0.25,
    "seo": 0.20,
    "accessibility": 0.15,
    "ux": 0.10,
}

PRIMARY_DARK = colors.HexColor("#1A2B3C")
ACCENT_BLUE = colors.HexColor("#3498DB")
SUCCESS_GREEN = colors.HexColor("#27AE60")
CRITICAL_RED = colors.HexColor("#C0392B")
WARNING_ORANGE = colors.HexColor("#F39C12")
MUTED_GREY = colors.HexColor("#7F8C8D")

USER_AGENT = 'FF-Tech-Audit-SaaS/5.0 (Railway-Node)'

# =========================================
# LOGGING
# =========================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit")

# =========================================
# UTILITIES
# =========================================
STOPWORDS = set(
    """a an and are as at be but by for if in into is it no not of on or such that the their then there these they this to was will with you your from our""".split()
)


def safe_get(url: str, headers: Optional[dict] = None, timeout: int = 15, allow_redirects: bool = True, method: str = "GET"):
    try:
        if method.upper() == "HEAD":
            return requests.head(url, headers=headers or {"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=allow_redirects)
        elif method.upper() == "OPTIONS":
            return requests.options(url, headers=headers or {"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=allow_redirects)
        else:
            return requests.get(url, headers=headers or {"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=allow_redirects)
    except Exception as e:
        logger.debug(f"safe_get error for {url}: {e}")
        return None


def get_domain(host_or_url: str) -> str:
    parsed = urlparse(host_or_url if host_or_url.startswith("http") else f"https://{host_or_url}")
    return parsed.netloc.lower()


def get_ip(domain: str) -> Optional[str]:
    try:
        return socket.gethostbyname(domain)
    except Exception:
        return None


def get_ssl_cert_expiry(domain: str, port: int = 443) -> Optional[str]:
    """Return SSL notAfter in RFC2822-like string if available."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                # 'notAfter' example: 'Mar 10 12:00:00 2027 GMT'
                return cert.get('notAfter')
    except Exception:
        return None


def https_redirected(initial_url: str, final_url: str) -> str:
    try:
        i = urlparse(initial_url)
        f = urlparse(final_url)
        if i.scheme == "http" and f.scheme == "https":
            return "Yes"
        return "No"
    except Exception:
        return "Unknown"


def count_minified(urls: List[str]) -> Tuple[int, int]:
    total = len(urls)
    minified = sum(1 for u in urls if ".min." in u)
    return minified, total


def classify_link(base_domain: str, href: str) -> str:
    try:
        d = urlparse(href)
        if not d.netloc or d.netloc == base_domain:
            return "Internal"
        return "External"
    except Exception:
        return "Unknown"


def resolve_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def estimate_business_impact(issue_cat: str, severity: str) -> str:
    sev = severity.lower()
    if issue_cat.lower() in ("sec", "security"):
        if "🔴" in severity or "critical" in sev:
            return "High risk: potential data exposure, trust loss"
        if "🟠" in severity or "high" in sev:
            return "Elevated risk: security misconfiguration"
        return "Moderate risk"
    if issue_cat.lower() in ("perf", "performance"):
        return "Conversion loss due to slow UX"
    if issue_cat.lower() in ("seo",):
        return "Lower organic traffic & visibility"
    if issue_cat.lower() in ("access", "accessibility"):
        return "Exclusion of users; potential compliance risk"
    if issue_cat.lower() in ("ux",):
        return "Reduced engagement & task completion"
    return "Operational impact"


# =========================================
# CORE AUDIT ENGINE
# =========================================
class SaaSWebAuditor:
    def __init__(self, url: str):
        self.url = url if url.startswith('http') else f"https://{url}"
        self.domain = get_domain(self.url)
        self.report_id = hashlib.sha256(f"{self.url}{time.time()}".encode()).hexdigest()[:12].upper()
        self.headers = {'User-Agent': USER_AGENT}
        self.findings: List[Dict[str, str]] = []
        self.debug: Dict[str, Any] = {}

    def _log_issue(self, cat: str, severity: str, msg: str, rec: str):
        self.findings.append({"cat": cat, "sev": severity, "msg": msg, "rec": rec})

    def _status(self, ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    def _yesno(self, ok: Optional[bool]) -> str:
        if ok is True:
            return "Yes"
        if ok is False:
            return "No"
        return "Unknown"

    def run_audit(self) -> Dict[str, Any]:
        try:
            t0 = time.time()
            res = safe_get(self.url, headers=self.headers, timeout=20, allow_redirects=True)
            if res is None:
                raise RuntimeError("Primary request failed")

            t_fetch_ms = (time.time() - t0) * 1000
            soup = BeautifulSoup(res.text or '', 'html.parser')
            final_url = res.url

            # ================= Performance =================
            p_score = 100
            if t_fetch_ms > 2000:
                p_score -= 25
                self._log_issue("Perf", "🔴 Critical", "Slow First Byte/Fetch time (>2s)", "Enable CDN/edge caching, tune server, optimize DB.")
            size_bytes = len(res.content or b'')
            if size_bytes > 2.5 * 1024 * 1024:  # 2.5 MB
                p_score -= 15
                self._log_issue("Perf", "🟠 High", "Heavy Page Weight (>2.5MB)", "Compress images, minify JS/CSS, remove unused assets.")

            # resources: approximate request count
            scripts = [resolve_url(final_url, s.get('src', '')) for s in soup.find_all('script') if s.get('src')]
            styles = [resolve_url(final_url, l.get('href', '')) for l in soup.find_all('link', rel=lambda v: v and 'stylesheet' in v) if l.get('href')]
            images = [resolve_url(final_url, i.get('src', '')) for i in soup.find_all('img') if i.get('src')]
            approx_requests = 1 + len(scripts) + len(styles) + len(images)
            if approx_requests > 80:
                p_score -= 10
                self._log_issue("Perf", "🟡 Medium", "High number of resource requests", "Bundle & defer assets; enable HTTP/2 or HTTP/3.")

            # compression
            enc = (res.headers.get('Content-Encoding') or '').lower()
            compression_enabled = enc in ("gzip", "br", "deflate")
            if not compression_enabled:
                p_score -= 5
                self._log_issue("Perf", "🟡 Medium", "Compression not enabled on HTML", "Enable GZIP/Brotli at CDN/server.")

            # caching
            cache_control = res.headers.get('Cache-Control', '')
            has_caching = any(k in cache_control.lower() for k in ["max-age", "s-maxage", "public"])
            if not has_caching:
                p_score -= 5
                self._log_issue("Perf", "🟡 Medium", "No explicit caching headers", "Add Cache-Control/ETag for static assets.")

            # minified assets ratio
            min_js, total_js = count_minified(scripts)
            min_css, total_css = count_minified(styles)

            # image optimization heuristic
            modern_images = sum(1 for u in images if any(u.lower().endswith(ext) for ext in [".webp", ".avif"]))
            img_opt_ok = modern_images >= max(1, int(0.3 * len(images))) if images else True
            if not img_opt_ok:
                p_score -= 5
                self._log_issue("Perf", "🟡 Medium", "Images not using modern formats", "Prefer WebP/AVIF; enable responsive images & lazy loading.")

            # lazy loading heuristic
            lazy_count = sum(1 for i in soup.find_all('img') if (i.get('loading') or '').lower() == 'lazy')
            lazy_ok = lazy_count >= max(1, int(0.3 * len(images))) if images else True

            # ================= SEO =================
            s_score = 100
            title_tag = soup.title.string.strip() if soup.title and soup.title.string else ''
            if not title_tag:
                s_score -= 30
                self._log_issue("SEO", "🔴 Critical", "Missing Title Tag", "Add a unique, keyword-optimized <title> (~55-60 chars).")
            else:
                if len(title_tag) < 20 or len(title_tag) > 65:
                    s_score -= 5
                    self._log_issue("SEO", "🟡 Medium", "Title length suboptimal", "Target 50–60 characters, include primary keyword.")

            meta_desc_el = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta_desc_el.get('content', '').strip() if meta_desc_el else ''
            if not meta_desc:
                s_score -= 20
                self._log_issue("SEO", "🟠 High", "Missing Meta Description", "Write a compelling 150–160 character summary.")
            else:
                if len(meta_desc) < 100 or len(meta_desc) > 180:
                    s_score -= 5
                    self._log_issue("SEO", "🟡 Medium", "Meta description length suboptimal", "Keep between 150–160 characters.")

            h1s = soup.find_all('h1')
            h2s = soup.find_all('h2')
            if len(h1s) == 0:
                s_score -= 10
                self._log_issue("SEO", "🟠 High", "Missing H1 heading", "Add one clear H1 per page with primary keyword.")

            canonical = soup.find('link', rel=lambda v: v and 'canonical' in v.lower())
            has_canonical = canonical is not None
            robots_meta = soup.find('meta', attrs={'name': 'robots'})
            robots_meta_content = (robots_meta.get('content') or '').lower() if robots_meta else ''
            indexable = ('noindex' not in robots_meta_content)

            robots_txt_url = f"{urlparse(final_url).scheme}://{self.domain}/robots.txt"
            robots_txt_res = safe_get(robots_txt_url, timeout=8)
            robots_txt_ok = (robots_txt_res is not None and robots_txt_res.status_code == 200)

            sitemap_present = False
            sitemap_url = f"{urlparse(final_url).scheme}://{self.domain}/sitemap.xml"
            sm_from_robots = False
            if robots_txt_ok:
                try:
                    if 'sitemap' in (robots_txt_res.text or '').lower():
                        sm_from_robots = True
                        sitemap_present = True
                except Exception:
                    pass
            sm_res = safe_get(sitemap_url, timeout=8)
            if sm_res is not None and sm_res.status_code == 200:
                sitemap_present = True

            # Open Graph & Twitter
            og_tags = soup.find_all('meta', attrs={'property': re.compile(r'^og:', re.I)})
            tw_tags = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:', re.I)})

            # ALT attributes
            imgs = soup.find_all('img')
            alt_missing = sum(1 for i in imgs if not i.get('alt'))

            # internal links & broken checks (sample)
            anchors = [a for a in soup.find_all('a') if a.get('href')]
            absolute_links = [(a.get_text(strip=True)[:60], resolve_url(final_url, a['href'])) for a in anchors]
            sampled = absolute_links[:40]  # limit for speed
            link_table = []
            for anchor_text, href in sampled:
                typ = classify_link(self.domain, href)
                r = safe_get(href, timeout=6, allow_redirects=True)
                status = r.status_code if (r is not None and hasattr(r, 'status_code')) else 'ERR'
                link_table.append({"url": href, "status": status, "anchor": anchor_text, "type": typ})
            broken_internal = [l for l in link_table if l['type'] == 'Internal' and isinstance(l['status'], int) and l['status'] >= 400]
            broken_external = [l for l in link_table if l['type'] == 'External' and isinstance(l['status'], int) and l['status'] >= 400]
            if broken_internal:
                s_score -= 10
                self._log_issue("SEO", "🟠 High", f"Broken internal links detected ({len(broken_internal)})", "Fix or remove broken links; set proper 301s.")

            # Technical SEO extras
            mobile_meta = soup.find('meta', attrs={'name': 'viewport'}) is not None
            structured_data = soup.find('script', attrs={'type': 'application/ld+json'}) is not None
            redirect_chain_note = "Sampled via requests; deep crawl recommended"

            # ================= Security =================
            sec_score = 100
            headers_lower = {k.lower(): v for k, v in res.headers.items()}
            ssl_ok = final_url.startswith("https")
            if not ssl_ok:
                sec_score -= 50
                self._log_issue("Sec", "🔴 Critical", "Insecure Connection (HTTP)", "Install TLS certificate and force HTTPS.")

            csp_missing = 'content-security-policy' not in headers_lower
            if csp_missing:
                sec_score -= 15
                self._log_issue("Sec", "🟡 Medium", "Missing Content-Security-Policy", "Set CSP to mitigate XSS/data injection.")

            hsts = 'strict-transport-security' in headers_lower
            xfo = 'x-frame-options' in headers_lower
            xxss = 'x-xss-protection' in headers_lower or 'x-xss-protection' in headers_lower
            xcto = 'x-content-type-options' in headers_lower

            # Mixed content
            mixed_issues = []
            if final_url.startswith('https'):
                http_resources = [u for u in scripts + styles + images if u.startswith('http://')]
                if http_resources:
                    sec_score -= 10
                    mixed_issues = http_resources[:10]
                    self._log_issue("Sec", "🟠 High", "Mixed content (HTTP assets on HTTPS page)", "Serve all assets over HTTPS.")

            # Admin panels exposed (heuristic)
            admin_paths = ["/admin", "/wp-admin", "/login", "/user/login"]
            exposed_admin = []
            base_root = f"{urlparse(final_url).scheme}://{self.domain}"
            for p in admin_paths:
                r = safe_get(base_root + p, timeout=5)
                if r is not None and r.status_code in (200, 401, 403):
                    exposed_admin.append(base_root + p)
            if exposed_admin:
                sec_score -= 5
                self._log_issue("Sec", "🟡 Medium", "Admin endpoints exposed", "Restrict access (IP allowlist, auth, obscure paths).")

            # HTTP methods allowed
            opt = safe_get(base_root, timeout=6, method="OPTIONS")
            allow_hdr = (opt.headers.get('Allow') if opt else '') if hasattr(opt, 'headers') else ''

            # Cookies flags
            set_cookies = res.headers.get('Set-Cookie', '')
            insecure_cookies = []
            for chunk in set_cookies.split(','):
                if '=' in chunk:
                    if 'secure' not in chunk.lower() or 'httponly' not in chunk.lower():
                        insecure_cookies.append(chunk.strip().split(';')[0])
            if insecure_cookies:
                sec_score -= 5
                self._log_issue("Sec", "🟡 Medium", "Cookies missing Secure/HttpOnly", "Mark cookies as Secure & HttpOnly; set SameSite.")

            # SSL certificate expiry
            ssl_expiry = get_ssl_cert_expiry(self.domain) if final_url.startswith('https') else None

            # ================= Accessibility =================
            a11y_score = 100
            if alt_missing > 0:
                a11y_score -= min(20, alt_missing)
                self._log_issue("Access", "🟡 Medium", f"{alt_missing} images missing ALT", "Provide descriptive alt text for images.")

            # Simple form label check
            inputs = soup.find_all('input')
            labels = soup.find_all('label')
            label_for = {l.get('for') for l in labels if l.get('for')}
            unlabeled_inputs = [i for i in inputs if (i.get('id') and i.get('id') not in label_for)]
            if unlabeled_inputs:
                a11y_score -= 10
                self._log_issue("Access", "🟡 Medium", "Form inputs without labels", "Associate <label for> with input id; use ARIA when needed.")

            # ARIA presence heuristic
            aria_present = any(attr for attr in soup.find_all(attrs={"aria-label": True}))

            # Semantic structure heuristic
            semantic_ok = any(soup.find(tag) for tag in ["header", "nav", "main", "article", "footer"]) or False

            # Compliance level estimate
            if a11y_score >= 90:
                a11y_level = "WCAG A (est.)"
            elif a11y_score >= 75:
                a11y_level = "WCAG AA (est.)"
            else:
                a11y_level = "Below AA (est.)"

            # ================= UX =================
            ux_score = 100
            if not mobile_meta:
                ux_score -= 15
                self._log_issue("UX", "🟠 High", "Missing viewport meta for mobile", "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.")

            # CTA heuristic
            cta_texts = ["buy", "get started", "contact", "signup", "sign up", "try", "demo", "start"]
            ctas = [a for a in anchors if any(t in (a.get_text(" ").strip().lower()) for t in cta_texts)]
            if not ctas:
                ux_score -= 5
                self._log_issue("UX", "🟡 Medium", "No prominent call-to-action detected", "Add clear CTA buttons above the fold.")

            # Broken buttons heuristic
            broken_buttons = [a for a in anchors if a.get('href') in ('#', 'javascript:void(0)')]
            if broken_buttons:
                ux_score -= 5
                self._log_issue("UX", "🟡 Medium", "Links/buttons without destination", "Provide valid destinations or click handlers.")

            # ================= CMS / Tracking =================
            generator_meta = soup.find('meta', attrs={'name': 'generator'})
            generator_val = (generator_meta.get('content') or '').lower() if generator_meta else ''
            cms = "Custom/Unknown"
            html_text = res.text.lower() if res.text else ''
            if "wp-content" in html_text or "wordpress" in generator_val:
                cms = "WordPress"
            elif "shopify" in html_text or "x-shopify-stage" in ''.join(res.headers.keys()).lower():
                cms = "Shopify"
            elif "wix" in html_text:
                cms = "Wix (heuristic)"

            # Tracking detection
            tracking = {
                "ga4": bool(re.search(r"G-[-A-Z0-9]{6,}", res.text or '', re.I)) or ("gtag/js" in html_text),
                "ua": bool(re.search(r"UA-\\d{4,}-\\d+", res.text or '', re.I)),
                "gtm": bool(re.search(r"GTM-[A-Z0-9]{5,}", res.text or '', re.I)),
                "fb_pixel": "fbq(" in html_text or "connect.facebook.net/en_US/fbevents.js" in html_text,
                "conversion": any(k in html_text for k in ["conversion", "purchase", "gtm.ecommerce"]),
            }

            # ================= Scoring Aggregate =================
            scores = {
                "performance": max(0, min(100, p_score)),
                "seo": max(0, min(100, s_score)),
                "security": max(0, min(100, sec_score)),
                "accessibility": max(0, min(100, a11y_score)),
                "ux": max(0, min(100, ux_score)),
            }
            overall = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

            # Risk level
            if overall >= 85:
                risk_level = "Low"
            elif overall >= 70:
                risk_level = "Medium"
            elif overall >= 50:
                risk_level = "High"
            else:
                risk_level = "Critical"

            # Top 5 critical issues
            critical_sorted = sorted(self.findings, key=lambda x: (0 if '🔴' in x['sev'] else 1, 0 if '🟠' in x['sev'] else 1))
            top5 = critical_sorted[:5]
            impact_notes = [
                {
                    **iss,
                    "impact": estimate_business_impact(iss['cat'], iss['sev'])
                }
                for iss in top5
            ]

            # Overview
            ip = get_ip(self.domain)
            ssl_status = "Valid (expiry: %s)" % ssl_expiry if (ssl_expiry is not None) else ("N/A" if not ssl_ok else "Unknown validity")
            redirect_http_to_https = https_redirected(self.url, final_url)

            overview = {
                "domain": self.domain,
                "ip": ip or "Unknown",
                "hosting_provider": "N/A (not detected)",
                "server_location": "N/A (requires geo-IP API)",
                "cms": cms,
                "ssl_status": ssl_status,
                "http_to_https": redirect_http_to_https,
                "page_load_time_ms": int(t_fetch_ms),
                "page_size_kb": round(size_bytes / 1024.0, 1),
                "total_requests_approx": approx_requests,
            }

            # Mixed content sample truncated to 10
            mixed_sample = mixed_issues

            # Accessibility details
            a11y_details = {
                "missing_alt": alt_missing,
                "contrast_issues": "N/A (requires color analysis)",
                "missing_aria_labels": "Heuristic: %s" % ("Some present" if aria_present else "Few/None detected"),
                "form_label_issues": len(unlabeled_inputs),
                "keyboard_support": "N/A (requires interaction test)",
                "semantic_html": "Good" if semantic_ok else "Needs improvement",
                "compliance_level": a11y_level,
            }

            # Performance details
            perf_details = {
                "fcp": "N/A (lab tool required)",
                "lcp": "N/A (lab tool required)",
                "tti": "N/A (lab tool required)",
                "total_blocking_time": "N/A (lab tool required)",
                "pagespeed": "N/A (API not integrated)",
                "compression": self._yesno(compression_enabled),
                "caching": self._yesno(has_caching),
                "minified_js": f"{min_js}/{total_js}",
                "minified_css": f"{min_css}/{total_css}",
                "image_optimization": self._yesno(img_opt_ok),
                "lazy_loading": self._yesno(lazy_ok),
            }

            # SEO details
            seo_details = {
                "title": title_tag,
                "title_length": len(title_tag) if title_tag else 0,
                "meta_description_length": len(meta_desc) if meta_desc else 0,
                "h1_count": len(h1s),
                "h2_count": len(h2s),
                "canonical_present": self._yesno(has_canonical),
                "robots_txt": self._yesno(robots_txt_ok),
                "sitemap_xml": self._yesno(sitemap_present),
                "open_graph": self._yesno(len(og_tags) > 0),
                "twitter_cards": self._yesno(len(tw_tags) > 0),
                "images_missing_alt": alt_missing,
                "broken_internal_links": len(broken_internal),
                "indexable": self._yesno(indexable),
                "mobile_responsive": self._yesno(mobile_meta),
                "core_web_vitals": "N/A (API not integrated)",
                "structured_data": self._yesno(structured_data),
                "redirect_chains": redirect_chain_note,
                "duplicate_content": "N/A (requires crawl)"
            }

            # Security details
            sec_details = {
                "ssl_certificate_validity": ssl_status,
                "hsts_enabled": self._yesno(hsts),
                "security_headers": {
                    "Content-Security-Policy": self._yesno(!csp_missing) if False else self._yesno(not csp_missing),
                    "X-Frame-Options": self._yesno(xfo),
                    "X-XSS-Protection": self._yesno(xxss),
                    "X-Content-Type-Options": self._yesno(xcto),
                },
                "mixed_content_sample": mixed_sample,
                "exposed_admin_panels": exposed_admin[:5],
                "http_methods_allowed": allow_hdr or "Unknown",
                "cookies_secure_httponly": self._yesno(len(insecure_cookies) == 0),
            }

            # UX details
            ux_details = {
                "mobile_friendly": self._yesno(mobile_meta),
                "viewport_configured": self._yesno(mobile_meta),
                "navigation_clarity": "Heuristic: nav present" if soup.find('nav') else "Needs review",
                "cta_visibility": "Heuristic: present" if ctas else "Low",
                "popup_intrusiveness": "N/A (dynamic behavior)",
                "broken_buttons": len(broken_buttons),
                "form_usability": "Heuristic: labels missing" if unlabeled_inputs else "Good",
            }

            # Broken links table (combine internal/external)
            broken_table = [l for l in link_table if isinstance(l['status'], int) and l['status'] >= 400]

            # Analytics & Tracking
            tracking_details = {
                "ga4_detected": self._yesno(tracking["ga4"]),
                "ua_detected": self._yesno(tracking["ua"]),
                "gtm_detected": self._yesno(tracking["gtm"]),
                "facebook_pixel": self._yesno(tracking["fb_pixel"]),
                "conversion_tracking": self._yesno(tracking["conversion"]),
                "missing_tracking": "Review if none detected",
            }

            data = {
                "meta": {
                    "url": self.url,
                    "final_url": final_url,
                    "domain": self.domain,
                    "id": self.report_id,
                    "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "overall": round(overall, 1),
                    "risk": risk_level,
                },
                "scores": scores,
                "issues": self.findings,
                "top_issues": impact_notes,
                "overview": overview,
                "seo": seo_details,
                "performance": perf_details,
                "security": sec_details,
                "accessibility": a11y_details,
                "ux": ux_details,
                "broken_links": broken_table,
                "tracking": tracking_details,
            }
            return data
        except Exception as e:
            return {"error": str(e)}


# =========================================
# PDF & VISUALIZATION GENERATOR
# =========================================
class ReportGenerator:
    def __init__(self, data: Dict[str, Any], logo_path: Optional[str] = None):
        self.data = data
        self.logo_path = logo_path
        self.styles = getSampleStyleSheet()
        # Tweak base styles
        self.styles.add(ParagraphStyle('SmallMuted', fontSize=8, textColor=MUTED_GREY))
        self.styles.add(ParagraphStyle('H2', parent=self.styles['Heading2'], textColor=PRIMARY_DARK))
        self.styles.add(ParagraphStyle('H3', parent=self.styles['Heading3'], textColor=PRIMARY_DARK))

    # ---------- Charts ----------
    def _radar_chart(self) -> io.BytesIO:
        labels = [k.upper() for k in WEIGHTS.keys()]
        stats = [self.data['scores'][k.lower()] for k in labels]

        angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
        stats += stats[:1]
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(4.8, 4.8), subplot_kw=dict(polar=True))
        ax.fill(angles, stats, color='#3498DB', alpha=0.25)
        ax.plot(angles, stats, color='#2980B9', linewidth=2)
        ax.set_yticklabels([])
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=9, fontweight='bold')
        fig.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', transparent=True, dpi=140)
        plt.close(fig)
        buf.seek(0)
        return buf

    def _bar_chart(self) -> io.BytesIO:
        cats = list(self.data['scores'].keys())
        vals = [self.data['scores'][c] for c in cats]
        fig, ax = plt.subplots(figsize=(5.6, 3.2))
        bars = ax.bar([c.upper() for c in cats], vals, color=['#2E86C1', '#1ABC9C', '#C0392B', '#8E44AD', '#F39C12'])
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

    # ---------- PDF Sections ----------
    def _cover_page(self, elems: List[Any]):
        elems.append(Spacer(1, 0.6*inch))
        # Logo (optional)
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                elems.append(Image(self.logo_path, width=1.8*inch, height=1.8*inch))
                elems.append(Spacer(1, 0.2*inch))
            except Exception:
                pass

        elems.append(Paragraph(COMPANY.upper(), ParagraphStyle('C1', fontSize=28, textColor=PRIMARY_DARK, fontName='Helvetica-Bold')))
        elems.append(Paragraph("Website Performance & Compliance Dossier", self.styles['Title']))
        elems.append(Spacer(1, 0.25*inch))

        meta = self.data['meta']
        cover_rows = [
            ["Website URL Audited", meta['final_url']],
            ["Audit Date & Time", meta['timestamp']],
            ["Report ID", meta['id']],
            ["Generated By", SAAS_NAME],
        ]
        t = Table(cover_rows, colWidths=[2.1*inch, 4.0*inch])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 0.2*inch))

        # QR to target
        qr_code = qr.QrCodeWidget(meta['final_url'])
        bounds = qr_code.getBounds()
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        d = Drawing(100, 100, transform=[100.0/w, 0, 0, 100.0/h, 0, 0])
        d.add(qr_code)
        elems.append(d)
        elems.append(Spacer(1, 0.2*inch))

        # Confidentiality notice
        notice = (
            "This report contains confidential and proprietary information intended solely for the recipient. "
            "Unauthorized distribution is prohibited."
        )
        elems.append(Paragraph(notice, self.styles['SmallMuted']))
        elems.append(PageBreak())

    def _executive_summary(self, elems: List[Any]):
        elems.append(Paragraph("Executive Health Summary", self.styles['Heading1']))
        meta = self.data['meta']
        scores = self.data['scores']

        # Summary stats
        rows = [
            ["Overall Website Health Score", f"{meta['overall']} / 100"],
            ["Overall Risk Level", meta['risk']],
            ["SEO Score", f"{scores['seo']}"],
            ["Performance Score", f"{scores['performance']}"],
            ["Security Score", f"{scores['security']}"],
            ["Accessibility Score", f"{scores['accessibility']}"],
            ["UX Score", f"{scores['ux']}"],
        ]
        st = Table(rows, colWidths=[2.5*inch, 3.6*inch])
        st.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ]))

        # Charts side-by-side
        radar = Image(self._radar_chart(), width=2.8*inch, height=2.8*inch)
        bars = Image(self._bar_chart(), width=3.6*inch, height=2.2*inch)

        chart_table = Table([[radar, bars]], colWidths=[3.0*inch, 3.2*inch])
        chart_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))

        elems.append(KeepTogether([chart_table, Spacer(1, 0.2*inch), st]))
        elems.append(Spacer(1, 0.15*inch))

        # Top 5 Critical Issues + Impact
        elems.append(Paragraph("Top 5 Critical Issues & Estimated Business Impact", self.styles['H2']))
        issues = self.data.get('top_issues', [])
        if not issues:
            elems.append(Paragraph("No critical issues detected.", self.styles['Normal']))
        else:
            issue_rows = [["Severity", "Type", "Finding", "Impact"]]
            for i in issues:
                issue_rows.append([i['sev'], i['cat'], i['msg'], i.get('impact', '')])
            it = Table(issue_rows, colWidths=[0.8*inch, 0.7*inch, 2.9*inch, 1.8*inch])
            it.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), ACCENT_BLUE),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                ('FONTSIZE', (0,0), (-1,-1), 8),
            ]))
            elems.append(it)
        elems.append(PageBreak())

    def _website_overview(self, elems: List[Any]):
        elems.append(Paragraph("Website Overview", self.styles['Heading1']))
        o = self.data['overview']
        rows = [
            ["Domain Name", o['domain']],
            ["IP Address", o['ip']],
            ["Hosting Provider", o['hosting_provider']],
            ["Server Location", o['server_location']],
            ["CMS Detected", o['cms']],
            ["SSL Status", o['ssl_status']],
            ["HTTP → HTTPS redirect", o['http_to_https']],
            ["Page Load Time", f"{o['page_load_time_ms']} ms"],
            ["Page Size", f"{o['page_size_kb']} KB"],
            ["Total Requests (approx)", str(o['total_requests_approx'])],
        ]
        t = Table(rows, colWidths=[2.2*inch, 3.9*inch])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        elems.append(t)
        elems.append(PageBreak())

    def _seo_section(self, elems: List[Any]):
        elems.append(Paragraph("SEO Audit", self.styles['Heading1']))
        s = self.data['seo']
        # On-Page SEO table
        elems.append(Paragraph("On-Page SEO", self.styles['H2']))
        on_rows = [
            ["Title tag (length)", f"{s['title_length']}"],
            ["Meta description (length)", f"{s['meta_description_length']}"],
            ["H1 count", f"{s['h1_count']}"],
            ["H2 count", f"{s['h2_count']}"],
            ["Canonical tag", s['canonical_present']],
            ["Robots.txt", s['robots_txt']],
            ["Sitemap.xml", s['sitemap_xml']],
            ["Open Graph tags", s['open_graph']],
            ["Twitter Card tags", s['twitter_cards']],
            ["Image ALT missing", str(s['images_missing_alt'])],
            ["Broken internal links", str(s['broken_internal_links'])],
        ]
        ot = Table(on_rows, colWidths=[3.0*inch, 3.1*inch])
        ot.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        elems.append(ot)
        elems.append(Spacer(1, 0.15*inch))

        # Technical SEO
        elems.append(Paragraph("Technical SEO", self.styles['H2']))
        tech_rows = [
            ["Indexability", s['indexable']],
            ["Mobile responsiveness", s['mobile_responsive']],
            ["Core Web Vitals", s['core_web_vitals']],
            ["Structured data (Schema.org)", s['structured_data']],
            ["Redirect chains", s['redirect_chains']],
            ["Duplicate content", s['duplicate_content']],
        ]
        tt = Table(tech_rows, colWidths=[3.0*inch, 3.1*inch])
        tt.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        elems.append(tt)
        elems.append(PageBreak())

    def _performance_section(self, elems: List[Any]):
        elems.append(Paragraph("Performance Audit", self.styles['Heading1']))
        p = self.data['performance']
        rows = [
            ["First Contentful Paint (FCP)", p['fcp']],
            ["Largest Contentful Paint (LCP)", p['lcp']],
            ["Time to Interactive (TTI)", p['tti']],
            ["Total Blocking Time", p['total_blocking_time']],
            ["PageSpeed score", p['pagespeed']],
            ["Compression enabled (GZIP/Brotli)", p['compression']],
            ["Caching headers", p['caching']],
            ["Minified JS", p['minified_js']],
            ["Minified CSS", p['minified_css']],
            ["Image optimization status", p['image_optimization']],
            ["Lazy loading status", p['lazy_loading']],
        ]
        t = Table(rows, colWidths=[3.5*inch, 2.6*inch])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        elems.append(t)
        elems.append(PageBreak())

    def _security_section(self, elems: List[Any]):
        elems.append(Paragraph("Security Audit", self.styles['Heading1']))
        s = self.data['security']
        rows = [
            ["SSL Certificate Validity", s['ssl_certificate_validity']],
            ["HSTS Enabled?", s['hsts_enabled']],
            ["Content-Security-Policy", s['security_headers']['Content-Security-Policy']],
            ["X-Frame-Options", s['security_headers']['X-Frame-Options']],
            ["X-XSS-Protection", s['security_headers']['X-XSS-Protection']],
            ["X-Content-Type-Options", s['security_headers']['X-Content-Type-Options']],
            ["Mixed content issues (sample)", "Yes" if s['mixed_content_sample'] else "No"],
            ["Exposed admin panels (sample)", ", ".join(s['exposed_admin_panels']) or "None"],
            ["HTTP methods allowed", s['http_methods_allowed']],
            ["Cookies secure/HttpOnly", s['cookies_secure_httponly']],
        ]
        t = Table(rows, colWidths=[3.2*inch, 2.9*inch])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        elems.append(t)

        if s['mixed_content_sample']:
            elems.append(Spacer(1, 0.15*inch))
            elems.append(Paragraph("Mixed Content (Sample)", self.styles['H3']))
            mc_rows = [["URL"]] + [[u] for u in s['mixed_content_sample']]
            mt = Table(mc_rows, colWidths=[6.1*inch])
            mt.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                ('FONTSIZE', (0,0), (-1,-1), 8),
            ]))
            elems.append(mt)
        elems.append(PageBreak())

    def _a11y_section(self, elems: List[Any]):
        elems.append(Paragraph("Accessibility Audit", self.styles['Heading1']))
        a = self.data['accessibility']
        rows = [
            ["Missing ALT tags", str(a['missing_alt'])],
            ["Contrast ratio issues", a['contrast_issues']],
            ["Missing ARIA labels", a['missing_aria_labels']],
            ["Form label issues", str(a['form_label_issues'])],
            ["Keyboard navigation support", a['keyboard_support']],
            ["Semantic HTML structure", a['semantic_html']],
            ["Compliance Level (est)", a['compliance_level']],
        ]
        t = Table(rows, colWidths=[3.2*inch, 2.9*inch])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        elems.append(t)
        elems.append(PageBreak())

    def _ux_section(self, elems: List[Any]):
        elems.append(Paragraph("User Experience (UX) Audit", self.styles['Heading1']))
        u = self.data['ux']
        rows = [
            ["Mobile friendliness", u['mobile_friendly']],
            ["Viewport configuration", u['viewport_configured']],
            ["Navigation clarity", u['navigation_clarity']],
            ["CTA visibility", u['cta_visibility']],
            ["Pop-up intrusiveness", u['popup_intrusiveness']],
            ["Broken buttons", str(u['broken_buttons'])],
            ["Form usability", u['form_usability']],
        ]
        t = Table(rows, colWidths=[3.2*inch, 2.9*inch])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        elems.append(t)
        elems.append(PageBreak())

    def _broken_links_section(self, elems: List[Any]):
        elems.append(Paragraph("Broken Link Analysis", self.styles['Heading1']))
        bl = self.data['broken_links']
        rows = [["URL", "Status Code", "Anchor Text", "Type"]]
        for l in bl[:60]:
            rows.append([l['url'], str(l['status']), l['anchor'], l['type']])
        t = Table(rows, colWidths=[3.1*inch, 0.9*inch, 1.3*inch, 0.8*inch])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ]))
        elems.append(t)
        elems.append(PageBreak())

    def _tracking_section(self, elems: List[Any]):
        elems.append(Paragraph("Analytics & Tracking", self.styles['Heading1']))
        t = self.data['tracking']
        rows = [
            ["Google Analytics (GA4)", t['ga4_detected']],
            ["Google Analytics (UA)", t['ua_detected']],
            ["Google Tag Manager", t['gtm_detected']],
            ["Facebook Pixel", t['facebook_pixel']],
            ["Conversion tracking", t['conversion_tracking']],
            ["Missing tracking warnings", t['missing_tracking']],
        ]
        tb = Table(rows, colWidths=[3.2*inch, 2.9*inch])
        tb.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ]))
        elems.append(tb)

    # Footer
    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.drawString(inch, 0.5*inch, f"{COMPANY} Security Signature: {self.data['meta']['id']}")
        canvas.drawRightString(A4[0]-inch, 0.5*inch, f"Page {doc.page}")
        canvas.restoreState()

    def generate_pdf(self, filename: str = "Enterprise_Audit_Report.pdf"):
        doc = SimpleDocTemplate(
            filename, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
        )
        elems: List[Any] = []

        self._cover_page(elems)
        self._executive_summary(elems)
        self._website_overview(elems)
        self._seo_section(elems)
        self._performance_section(elems)
        self._security_section(elems)
        self._a11y_section(elems)
        self._ux_section(elems)
        self._broken_links_section(elems)
        self._tracking_section(elems)

        doc.build(elems, onFirstPage=self._footer, onLaterPages=self._footer)


# =========================================
# MAIN EXECUTION (Example)
# =========================================
if __name__ == "__main__":
    TARGET = os.environ.get("AUDIT_TARGET", "https://www.google.com")
    LOGO = os.environ.get("AUDIT_LOGO", None)  # optional
    print(f"[*] Initializing Enterprise Audit for: {TARGET}")

    auditor = SaaSWebAuditor(TARGET)
    audit_data = auditor.run_audit()

    if "error" not in audit_data:
        report = ReportGenerator(audit_data, logo_path=LOGO)
        out_file = os.environ.get("AUDIT_OUT", "Enterprise_Audit_Report.pdf")
        report.generate_pdf(out_file)
        print(f"[+] Success! Report saved as: {out_file}")
    else:
        print(f"[!] Error during audit: {audit_data['error']}")
