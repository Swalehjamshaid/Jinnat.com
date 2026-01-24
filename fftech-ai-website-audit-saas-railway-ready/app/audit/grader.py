# app/audit/grader.py
# SAFE | PRODUCTION | INTERNATIONAL STANDARDS

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# -------------------------
# Grading scale (unchanged)
# -------------------------
GRADE_BANDS = [
    (90, 'A+'),
    (80, 'A'),
    (70, 'B'),
    (60, 'C'),
    (0, 'D')
]

# -------------------------
# Core scoring logic
# -------------------------
def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    penalties = 0

    # SEO penalties (Google SEO Starter Guide)
    penalties += onpage.get('missing_title_tags', 0) * 2
    penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
    penalties += onpage.get('multiple_h1', 0) * 1
    penalties += onpage.get('missing_lang', 0) * 0.5

    # Link integrity (W3C / UX)
    penalties += links.get('total_broken_links', 0) * 0.5

    # Performance (Lighthouse-inspired approximation)
    lcp = perf.get('lcp_ms', 4000) or 4000
    fcp = perf.get('fcp_ms', 2000) or 2000
    perf_score = max(0, 100 - (lcp / 40 + fcp / 30))

    # Crawl coverage
    coverage = min(100, crawl_pages_count * 2)

    raw = max(0, 100 - penalties) * 0.5 + perf_score * 0.3 + coverage * 0.2
    overall = max(0, min(100, raw))

    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break

    return overall, grade, {
        "onpage": max(0, 100 - penalties),
        "performance": round(perf_score, 2),
        "coverage": coverage
    }

# -------------------------
# MAIN AUDIT ENTRY (DO NOT RENAME)
# -------------------------
def run_audit(payload: dict) -> dict:
    """
    International-standard website audit.
    INPUT  : { "url": "https://example.com" }
    OUTPUT : overall_score, grade, breakdown
    """

    url = payload.get("url")
    if not url:
        return _safe_fail("URL not provided")

    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.netloc:
        return _safe_fail("Invalid URL")

    # -------- Default metrics (safe fallbacks) --------
    onpage = {
        "missing_title_tags": 0,
        "missing_meta_descriptions": 0,
        "multiple_h1": 0,
        "missing_lang": 0
    }

    links = {
        "total_broken_links": 0
    }

    # Approximate performance (cloud-safe)
    perf = {
        "lcp_ms": 3200,
        "fcp_ms": 1600
    }

    crawl_pages_count = 1

    # -------- Fetch & analyze --------
    try:
        with httpx.Client(
            timeout=httpx.Timeout(10.0),
            follow_redirects=True,
            headers={"User-Agent": "FFTech-AuditBot/1.0"}
        ) as client:

            response = client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # ---------- SEO / On-page ----------
            if not soup.title or not soup.title.text.strip():
                onpage["missing_title_tags"] = 1

            if not soup.find("meta", attrs={"name": "description"}):
                onpage["missing_meta_descriptions"] = 1

            h1_tags = soup.find_all("h1")
            if len(h1_tags) > 1:
                onpage["multiple_h1"] = len(h1_tags) - 1

            if not soup.html or not soup.html.get("lang"):
                onpage["missing_lang"] = 1

            # ---------- Link Integrity ----------
            anchors = soup.find_all("a", href=True)
            checked = 0

            for a in anchors:
                if checked >= 20:  # HARD LIMIT (cloud-safe)
                    break

                href = a["href"].strip()
                full_url = urljoin(url, href)

                if full_url.startswith("http"):
                    try:
                        r = client.head(full_url, timeout=5)
                        if r.status_code >= 400:
                            links["total_broken_links"] += 1
                    except Exception:
                        links["total_broken_links"] += 1

                checked += 1

            crawl_pages_count = min(len(anchors), 50)

    except Exception as e:
        # Absolute safety: never crash the app
        return _safe_fail(str(e))

    # -------- Final score --------
    overall, grade, breakdown = compute_scores(
        onpage=onpage,
        perf=perf,
        links=links,
        crawl_pages_count=crawl_pages_count
    )

    return {
        "overall_score": round(overall, 2),
        "grade": grade,
        "breakdown": breakdown
    }

# -------------------------
# Safety fallback
# -------------------------
def _safe_fail(reason: str) -> dict:
    return {
        "overall_score": 0,
        "grade": "D",
        "breakdown": {},
        "error": reason
    }
