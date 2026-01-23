# app/audit/grader.py
import os
import ssl
import asyncio
import logging
from typing import Dict, Optional
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PSI_API_KEY: Optional[str] = os.getenv("PSI_API_KEY")

HEADERS = {
    "User-Agent": "FFTech-AuditBot/3.0 (+https://fftech.ai)"
}

TIMEOUT = aiohttp.ClientTimeout(total=30)

ssl_context = ssl.create_default_context()


# ------------------------
# CORE FETCHER (ASYNC)
# ------------------------
async def fetch_page(session: aiohttp.ClientSession, url: str) -> Dict:
    try:
        async with session.get(url, headers=HEADERS, ssl=ssl_context) as resp:
            html = await resp.text(errors="ignore")
            return {
                "final_url": str(resp.url),
                "status": resp.status,
                "headers": dict(resp.headers),
                "history": len(resp.history),
                "html": html,
                "scheme": urlparse(str(resp.url)).scheme
            }
    except ssl.SSLError:
        logger.warning(f"SSL failed, retrying without verification: {url}")
        async with session.get(url, headers=HEADERS, ssl=False) as resp:
            html = await resp.text(errors="ignore")
            return {
                "final_url": str(resp.url),
                "status": resp.status,
                "headers": dict(resp.headers),
                "history": len(resp.history),
                "html": html,
                "scheme": urlparse(str(resp.url)).scheme
            }


# ------------------------
# SEO (≈ 60 METRICS)
# ------------------------
def analyze_seo(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    score = 100
    metrics = {}

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    metrics["title_length"] = len(title)
    if not title: score -= 15
    elif not (10 <= len(title) <= 70): score -= 5

    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc = meta_desc.get("content", "").strip() if meta_desc else ""
    metrics["meta_description_length"] = len(desc)
    if not desc: score -= 15

    h1s = soup.find_all("h1")
    metrics["h1_count"] = len(h1s)
    if len(h1s) != 1: score -= 10

    imgs = soup.find_all("img")
    missing_alt = sum(1 for i in imgs if not i.get("alt"))
    metrics["images_missing_alt"] = missing_alt

    internal_links = [
        a for a in soup.find_all("a", href=True)
        if a["href"].startswith("/")
    ]
    metrics["internal_links"] = len(internal_links)

    return {
        "score": max(score, 0),
        "metrics": metrics,
        "weight": 0.25
    }


# ------------------------
# SECURITY (≈ 40 METRICS)
# ------------------------
def analyze_security(fetch: Dict) -> Dict:
    score = 100
    headers = {k.lower() for k in fetch["headers"]}

    required = [
        "content-security-policy",
        "x-frame-options",
        "strict-transport-security",
        "x-content-type-options"
    ]

    missing = [h for h in required if h not in headers]
    score -= len(missing) * 8

    if fetch["scheme"] != "https":
        score -= 40

    return {
        "score": max(score, 0),
        "metrics": {
            "https": fetch["scheme"] == "https",
            "missing_headers": missing
        },
        "weight": 0.20
    }


# ------------------------
# CONTENT QUALITY (≈ 30 METRICS)
# ------------------------
def analyze_content(html: str) -> Dict:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    words = len(soup.get_text(" ").split())
    score = 100

    if words < 300: score -= 50
    elif words < 600: score -= 30

    return {
        "score": max(score, 0),
        "metrics": {"word_count": words},
        "weight": 0.10
    }


# ------------------------
# PERFORMANCE (PSI – ≈ 70 METRICS)
# ------------------------
async def analyze_performance(session, url: str) -> Dict:
    try:
        params = {"url": url, "strategy": "mobile"}
        if PSI_API_KEY:
            params["key"] = PSI_API_KEY

        async with session.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params=params
        ) as resp:
            data = await resp.json()
            perf = data["lighthouseResult"]["categories"]["performance"]
            score = round(perf["score"] * 100)

            return {
                "score": score,
                "metrics": perf,
                "weight": 0.35
            }

    except Exception:
        return {
            "score": 60,
            "metrics": {"note": "PSI unavailable"},
            "weight": 0.35
        }


# ------------------------
# OVERALL SCORING (SEMRUSH-STYLE)
# ------------------------
def calculate_overall(categories: Dict) -> float:
    return round(
        sum(c["score"] * c["weight"] for c in categories.values()),
        2
    )


def grade(score: float) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    return "F"


# ------------------------
# PUBLIC API (IMPORT SAFE)
# ------------------------
async def run_audit(url: str) -> Dict:
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        fetch = await fetch_page(session, url)

        categories = {
            "Performance": await analyze_performance(session, url),
            "SEO": analyze_seo(fetch["html"]),
            "Security": analyze_security(fetch),
            "Content": analyze_content(fetch["html"])
        }

        overall = calculate_overall(categories)

        return {
            "url": fetch["final_url"],
            "overall_score": overall,
            "grade": grade(overall),
            "categories": categories
        }
