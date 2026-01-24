# app/audit/psi.py
import http.client
from urllib.parse import urlparse
from typing import Dict
from html.parser import HTMLParser
import logging
import socket
import time

logger = logging.getLogger("python_audit")
logging.basicConfig(level=logging.INFO)

DEFAULT_RESULT: Dict[str, float] = {
    "performance": 0.0,
    "seo": 0.0,
    "accessibility": 0.0,
    "best_practices": 0.0,
    "lcp": 0.0,  # simulated load time in seconds
    "cls": 0.0,  # placeholder for layout stability
}

# ---------------------------
# HTML Parser for SEO & links
# ---------------------------
class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = False
        self.meta_description = False
        self.img_without_alt = 0
        self.links = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title":
            self.title = True
        elif tag == "meta" and attrs_dict.get("name") == "description":
            self.meta_description = True
        elif tag == "img" and not attrs_dict.get("alt"):
            self.img_without_alt += 1
        elif tag == "a":
            self.links += 1


# ---------------------------
# Utility Functions
# ---------------------------
def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    parsed = urlparse(u)
    if not parsed.scheme:
        u = "https://" + u
    return u

def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)

def _fetch_page(url: str, timeout: int = 5) -> str:
    """Fetch page HTML using only Python standard libraries."""
    parsed = urlparse(url)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    html = ""
    try:
        conn = conn_cls(parsed.netloc, timeout=timeout)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        start = time.time()
        conn.request("GET", path, headers={"User-Agent": "FFTechPythonAuditor/1.0"})
        resp = conn.getresponse()
        if resp.status >= 400:
            logger.warning("[PRE-AUDIT] HTTP %s for %s", resp.status, url)
            return ""
        html = resp.read().decode(errors="ignore")
        end = time.time()
        result_lcp = min(end - start, 5.0)  # simulate LCP (max 5s)
        return html, result_lcp
    except (http.client.HTTPException, socket.timeout, socket.gaierror) as e:
        logger.warning("[PRE-AUDIT] Failed to fetch %s: %s", url, e)
        return "", 0.0
    finally:
        try:
            conn.close()
        except:
            pass


# ---------------------------
# Python Pre-Audit
# ---------------------------
def python_library_audit(url: str) -> Dict[str, float]:
    """
    Run Python-only pre-audit:
    - URL validation
    - Page reachability
    - Simple SEO & accessibility checks
    """
    result = DEFAULT_RESULT.copy()
    target = _normalize_url(url)

    if not target or not _is_valid_url(target):
        logger.error("[PRE-AUDIT] Invalid URL: %s", url)
        return result

    html, lcp = _fetch_page(target)
    if not html:
        return result

    parser = SimpleHTMLParser()
    parser.feed(html)

    # --- Simple heuristics ---
    result["performance"] = max(0.0, 100 - lcp * 10)  # higher load time → lower score
    result["lcp"] = lcp
    result["cls"] = 0.0  # placeholder (no real layout shift info)
    result["seo"] = 30.0
    if parser.title:
        result["seo"] += 20.0
    if parser.meta_description:
        result["seo"] += 20.0
    result["accessibility"] = max(0.0, 100 - parser.img_without_alt * 10)
    result["best_practices"] = 50.0 + min(parser.links, 10) * 5  # encourage pages with links

    # Clamp all scores 0..100
    for k in result:
        result[k] = min(max(result[k], 0.0), 100.0)

    return result


# ---------------------------
# Full Audit Entry Point
# ---------------------------
async def full_audit(url: str) -> Dict[str, float]:
    """
    Fully Python-native audit workflow:
    1. Run Python pre-audit only (no external APIs)
    """
    return python_library_audit(url)


# ---------------------------
# Backward Compatibility Alias
# ---------------------------
fetch_lighthouse = full_audit
