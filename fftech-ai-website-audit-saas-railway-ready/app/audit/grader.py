import requests
import logging
from typing import Dict
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "FFTech-AuditBot/2.0 (+https://fftech.ai)"
}

TIMEOUT = 20


# -----------------------------
# CORE FETCH
# -----------------------------
def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


# -----------------------------
# SEO ANALYSIS
# -----------------------------
def analyze_seo(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")

    score = 100
    metrics = {}

    title = soup.title.string.strip() if soup.title else None
    metrics["title_present"] = bool(title)
    if not title:
        score -= 15
    elif len(title) < 10 or len(title) > 65:
        score -= 5

    meta_desc = soup.find("meta", attrs={"name": "description"})
    metrics["meta_description"] = bool(meta_desc)
    if not meta_desc:
        score -= 15

    h1_tags = soup.find_all("h1")
    metrics["h1_count"] = len(h1_tags)
    if len(h1_tags) != 1:
        score -= 10

    canonical = soup.find("link", rel="canonical")
    metrics["canonical_present"] = bool(canonical)
    if not canonical:
        score -= 5

    images = soup.find_all("img")
    missing_alt = sum(1 for img in images if not img.get("alt"))
    metrics["images_missing_alt"] = missing_alt
    if images and missing_alt / len(images) > 0.3:
        score -= 10

    return {
        "score": max(score, 0),
        "metrics": metrics,
        "color": "#22C55E" if score >= 80 else "#F59E0B"
    }


# -----------------------------
# SECURITY ANALYSIS
# -----------------------------
def analyze_security(url: str, response_headers: Dict) -> Dict:
    score = 100
    metrics = {}

    parsed = urlparse(url)
    metrics["https"] = parsed.scheme == "https"
    if parsed.scheme != "https":
        score -= 40

    headers_to_check = [
        "Content-Security-Policy",
        "X-Frame-Options",
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "Referrer-Policy"
    ]

    missing = []
    for h in headers_to_check:
        if h not in response_headers:
            missing.append(h)

    metrics["missing_security_headers"] = missing
    score -= len(missing) * 6

    return {
        "score": max(score, 0),
        "metrics": metrics,
        "color": "#0EA5E9" if score >= 80 else "#EF4444"
    }


# -----------------------------
# CONTENT QUALITY
# -----------------------------
def analyze_content(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    words = len(text.split())

    score = 100
    metrics = {"word_count": words}

    if words < 400:
        score -= 40
    elif words < 900:
        score -= 20

    return {
        "score": max(score, 0),
        "metrics": metrics,
        "color": "#10B981"
    }


# -----------------------------
# INTERNATIONALIZATION
# -----------------------------
def analyze_i18n(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    hreflang = soup.find_all("link", rel="alternate", hreflang=True)

    score = 90 if hreflang else 60
    return {
        "score": score,
        "metrics": {"hreflang_count": len(hreflang)},
        "color": "#6366F1"
    }


# -----------------------------
# PERFORMANCE (REAL PSI)
# -----------------------------
def analyze_performance(url: str) -> Dict:
    """
    Uses Google PageSpeed Insights (no key = public tier).
    """
    try:
        psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {"url": url, "strategy": "mobile"}
        res = requests.get(psi_url, params=params, timeout=TIMEOUT)
        data = res.json()

        lighthouse = data["lighthouseResult"]["categories"]["performance"]
        score = round(lighthouse["score"] * 100, 2)

        audits = data["lighthouseResult"]["audits"]
        metrics = {
            "lcp_ms": audits["largest-contentful-paint"]["numericValue"],
            "cls": audits["cumulative-layout-shift"]["numericValue"],
            "inp_ms": audits.get("interaction-to-next-paint", {}).get("numericValue"),
        }

        return {
            "score": score,
            "metrics": metrics,
            "color": "#3B82F6"
        }

    except Exception as e:
        logger.warning(f"PSI failed: {e}")
        return {
            "score": 70,
            "metrics": {"note": "PSI unavailable"},
            "color": "#94A3B8"
        }


# -----------------------------
# OVERALL SCORING
# -----------------------------
def calculate_overall_score(cats: Dict) -> float:
    return round(
        cats["Performance"]["score"] * 0.30 +
        cats["SEO"]["score"] * 0.25 +
        cats["Security"]["score"] * 0.20 +
        cats["Internationalization"]["score"] * 0.10 +
        cats["Content Quality"]["score"] * 0.15,
        2
    )


def assign_grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    return "C"


# -----------------------------
# MAIN ENTRY (HTML + PDF SAFE)
# -----------------------------
def run_audit(url: str) -> Dict:
    try:
        html = fetch_html(url)
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

        performance = analyze_performance(url)
        seo = analyze_seo(html)
        security = analyze_security(url, response.headers)
        i18n = analyze_i18n(html)
        content = analyze_content(html)

        categories = {
            "Performance": performance,
            "SEO": seo,
            "Security": security,
            "Internationalization": i18n,
            "Content Quality": content,
        }

        overall = calculate_overall_score(categories)
        grade = assign_grade(overall)

        return {
            "url": url,
            "overall_score": overall,
            "grade": grade,
            "categories": categories,
            "competitors": []
        }

    except Exception as e:
        logger.exception(f"AUDIT FAILED: {e}")
        return {
            "url": url,
            "overall_score": 0,
            "grade": "N/A",
            "categories": {},
            "competitors": []
        }
