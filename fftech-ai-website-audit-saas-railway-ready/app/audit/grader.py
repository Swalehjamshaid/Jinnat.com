import requests
import logging
from typing import Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import urllib3

# Suppress only InsecureRequestWarning when verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "FFTech-AuditBot/2.0 (+https://fftech.ai)"
}
TIMEOUT = (10, 25)  # connect, read timeouts

# Optional: Add your Google API key here for reliable PSI (strongly recommended)
# Get free key: https://console.cloud.google.com/apis/credentials
PSI_API_KEY: Optional[str] = None  # ← Set this to "your_key_here" if you have one


def fetch_page(url: str) -> requests.Response:
    """
    Unified fetch with SSL fallback and better error handling.
    Returns full Response object (for headers + text).
    """
    try:
        # First try with verification
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()
        return response
    except requests.exceptions.SSLError as ssl_err:
        logger.warning(f"SSL verification failed for {url}: {ssl_err}. Falling back to verify=False.")
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True,
                verify=False
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"Fetch failed even with verify=False for {url}: {e}")
            raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        raise


def analyze_seo(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    score = 100
    metrics = {}

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    metrics["title_present"] = bool(title)
    if not title:
        score -= 15
    elif len(title) < 10 or len(title) > 70:  # Slightly updated 2026 best practice range
        score -= 5

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag["content"].strip() if meta_desc_tag and "content" in meta_desc_tag.attrs else None
    metrics["meta_description_present"] = bool(meta_desc)
    if not meta_desc:
        score -= 15
    elif len(meta_desc) < 50 or len(meta_desc) > 160:
        score -= 3

    h1_tags = soup.find_all("h1")
    metrics["h1_count"] = len(h1_tags)
    if len(h1_tags) != 1:
        score -= 10

    canonical = soup.find("link", rel="canonical")
    metrics["canonical_present"] = bool(canonical)
    if not canonical:
        score -= 5

    images = soup.find_all("img")
    if images:
        missing_alt = sum(1 for img in images if not img.get("alt") or not img["alt"].strip())
        metrics["images_missing_alt_count"] = missing_alt
        metrics["images_total"] = len(images)
        if missing_alt / len(images) > 0.25:  # Slightly stricter
            score -= 10
    else:
        metrics["images_missing_alt_count"] = 0

    return {
        "score": max(score, 0),
        "metrics": metrics,
        "color": "#22C55E" if score >= 80 else "#F59E0B" if score >= 50 else "#EF4444"
    }


def analyze_security(url: str, response: requests.Response) -> Dict:
    score = 100
    metrics = {}
    parsed = urlparse(response.url)  # Use final URL after redirects
    metrics["https"] = parsed.scheme == "https"
    if not metrics["https"]:
        score -= 40

    headers_to_check = [
        "Content-Security-Policy",
        "X-Frame-Options",
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy"  # Added modern header
    ]
    missing = [h for h in headers_to_check if h.lower() not in {k.lower(): v for k, v in response.headers.items()}]
    metrics["missing_security_headers"] = missing
    score -= len(missing) * 7  # Slightly higher penalty

    # Bonus: Check if final URL == original (no sneaky redirects)
    metrics["redirect_chain_length"] = len(response.history)
    if len(response.history) > 2:
        score -= 10

    return {
        "score": max(score, 0),
        "metrics": metrics,
        "color": "#0EA5E9" if score >= 80 else "#EF4444"
    }


def analyze_content(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    words = len(text.split())
    score = 100
    metrics = {"word_count": words}
    if words < 300:
        score -= 50
    elif words < 600:
        score -= 30
    elif words < 1000:
        score -= 15
    return {
        "score": max(score, 0),
        "metrics": metrics,
        "color": "#10B981" if score >= 70 else "#F59E0B"
    }


def analyze_i18n(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    hreflang_tags = soup.find_all("link", rel="alternate", hreflang=True)
    x_default = any(link.get("hreflang") == "x-default" for link in hreflang_tags)
    count = len(hreflang_tags)
    score = 95 if count >= 2 and x_default else (80 if count >= 1 else 50)
    return {
        "score": score,
        "metrics": {"hreflang_count": count, "has_x_default": x_default},
        "color": "#6366F1" if score >= 80 else "#F97316"
    }


def analyze_performance(url: str) -> Dict:
    """
    Google PageSpeed Insights v5 – public access still possible (limited quota).
    Strongly recommend setting PSI_API_KEY for production use.
    """
    try:
        psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        params = {
            "url": url,
            "strategy": "mobile",
        }
        if PSI_API_KEY:
            params["key"] = PSI_API_KEY

        res = requests.get(psi_url, params=params, timeout=TIMEOUT)
        res.raise_for_status()
        data = res.json()

        if "lighthouseResult" not in data:
            raise ValueError("Missing lighthouseResult – possible quota/rate limit")

        lighthouse = data["lighthouseResult"]
        perf_category = lighthouse["categories"]["performance"]
        score = round(perf_category["score"] * 100)

        audits = lighthouse["audits"]
        metrics = {
            "lcp_ms": audits.get("largest-contentful-paint", {}).get("numericValue"),
            "cls": audits.get("cumulative-layout-shift", {}).get("numericValue"),
            "inp_ms": audits.get("interaction-to-next-paint", {}).get("numericValue") or
                      audits.get("max-potential-fid", {}).get("numericValue"),  # fallback
        }
        return {
            "score": score,
            "metrics": metrics,
            "color": "#3B82F6" if score >= 90 else "#10B981" if score >= 50 else "#EF4444"
        }
    except Exception as e:
        logger.warning(f"PSI failed for {url}: {str(e)}")
        return {
            "score": 60,
            "metrics": {"note": "PageSpeed Insights unavailable (quota, network, or API change)"},
            "color": "#94A3B8"
        }


def calculate_overall_score(cats: Dict) -> float:
    return round(
        cats["Performance"]["score"] * 0.35 +      # Performance often most important
        cats["SEO"]["score"] * 0.25 +
        cats["Security"]["score"] * 0.20 +
        cats["Content Quality"]["score"] * 0.10 +
        cats["Internationalization"]["score"] * 0.10,
        2
    )


def assign_grade(score: float) -> str:
    if score >= 90: return "A+"
    if score >= 85: return "A"
    if score >= 75: return "B+"
    if score >= 65: return "B"
    if score >= 50: return "C"
    return "F"


def run_audit(url: str) -> Dict:
    try:
        response = fetch_page(url)
        html = response.text

        performance = analyze_performance(url)
        seo = analyze_seo(html)
        security = analyze_security(url, response)  # Use final response
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
            "url": response.url,  # Final URL after redirects
            "overall_score": overall,
            "grade": grade,
            "categories": categories,
            "competitors": []  # Placeholder – add logic if needed
        }
    except Exception as e:
        logger.exception(f"AUDIT FAILED for {url}: {e}")
        return {
            "url": url,
            "overall_score": 0,
            "grade": "N/A",
            "categories": {},
            "competitors": [],
            "error": str(e)
        }
