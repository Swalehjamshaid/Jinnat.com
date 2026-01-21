import httpx
import asyncio
import google.generativeai as genai
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urljoin

from .crawler import crawl_site
from .utils import clamp, invert_scale
from ..config import settings

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')  # Use newer model for better results


async def fetch_pagespeed_insights(url: str, strategy: str = "desktop") -> Dict:
    """Fetch real Core Web Vitals from Google PageSpeed Insights API (no API key needed)"""
    api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": url, "strategy": strategy, "category": ["performance"]}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            lighthouse = data.get("lighthouseResult", {})
            audits = lighthouse.get("audits", {})
            return {
                "lcp": audits.get("largest-contentful-paint", {}).get("numericValue", None),
                "cls": audits.get("cumulative-layout-shift", {}).get("numericValue", None),
                "fid": audits.get("max-potential-fid", {}).get("numericValue", None),  # or "total-blocking-time"
                "fcp": audits.get("first-contentful-paint", {}).get("numericValue", None),
                "speed_index": audits.get("speed-index", {}).get("numericValue", None),
                "tbt": audits.get("total-blocking-time", {}).get("numericValue", None),
                "score": lighthouse.get("categories", {}).get("performance", {}).get("score", None) * 100,
            }
    except Exception as e:
        print(f"PageSpeed Insights failed: {e}")
        return {}


async def analyze(url: str, competitors: List[str] = None) -> Dict[str, Any]:
    """
    Comprehensive AI Website Audit Engine
    Covers major parts of Categories A–I (expandable to 200 metrics)
    """
    competitors = competitors or []
    base_url = url.rstrip("/")

    # ── 1. Crawl & Gather Raw Data (Categories B, C, H) ─────────────────────────
    pages = await crawl_site(base_url, max_pages=50)  # Increase limit as needed
    total_pages = len(pages)

    if total_pages == 0:
        raise ValueError(f"Failed to crawl {url}")

    # Initialize structured metrics
    metrics: Dict[str, Any] = {
        # B. Overall Site Health
        "total_pages_crawled": total_pages,
        "total_errors": 0,
        "total_warnings": 0,
        "total_notices": 0,

        # C. Crawlability & Indexation
        "status_2xx": 0,
        "status_3xx": 0,
        "status_4xx": 0,
        "status_5xx": 0,
        "broken_internal_links": 0,
        "broken_external_links": 0,
        "redirect_chains": 0,  # stub - expand later

        # D. On-Page SEO
        "missing_title": 0,
        "missing_meta_desc": 0,
        "missing_h1": 0,
        "multiple_h1": 0,
        "img_no_alt": 0,
        "thin_content_pages": 0,  # text < 300 chars

        # E. Performance & Technical
        "page_size_bytes": 0,
        "core_web_vitals": {},

        # F. Mobile/Security/International (partial)
        "https_pages": 0,

        # H. Broken Links Intelligence
        "total_broken_links": 0,
    }

    # ── 2. Process Crawled Pages ────────────────────────────────────────────────
    for page in pages:
        status = page.get("status", 0)
        html = page.get("html", "")
        url_parsed = urlparse(page.get("url", ""))

        # Status codes
        if 200 <= status < 300:
            metrics["status_2xx"] += 1
            if url_parsed.scheme == "https":
                metrics["https_pages"] += 1
        elif 300 <= status < 400:
            metrics["status_3xx"] += 1
        elif 400 <= status < 500:
            metrics["status_4xx"] += 1
            metrics["broken_internal_links"] += 1 if url in page.get("url", "") else 0
            metrics["total_broken_links"] += 1
        else:
            metrics["status_5xx"] += 1

        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")

        # On-Page SEO (D)
        if not soup.title:
            metrics["missing_title"] += 1
        if not soup.find("meta", attrs={"name": "description"}):
            metrics["missing_meta_desc"] += 1
        h1_count = len(soup.find_all("h1"))
        if h1_count == 0:
            metrics["missing_h1"] += 1
        if h1_count > 1:
            metrics["multiple_h1"] += 1

        # Images
        for img in soup.find_all("img"):
            if not img.get("alt"):
                metrics["img_no_alt"] += 1

        # Thin content (simple heuristic)
        text = soup.get_text(separator=" ", strip=True)
        if len(text) < 300:
            metrics["thin_content_pages"] += 1

        # Page size
        metrics["page_size_bytes"] += len(html.encode("utf-8"))

    metrics["avg_page_size_kb"] = round(metrics["page_size_bytes"] / (total_pages * 1024), 2)

    # ── 3. Real Performance Data (E) ────────────────────────────────────────────
    psi_data = await fetch_pagespeed_insights(url, "desktop")
    psi_mobile = await fetch_pagespeed_insights(url, "mobile")
    metrics["core_web_vitals"] = {
        "desktop": psi_data,
        "mobile": psi_mobile,
    }

    # ── 4. Category Scoring (0–100) ─────────────────────────────────────────────
    category_scores = {
        "crawlability": clamp(100 - (metrics["status_4xx"] * 8) - (metrics["status_5xx"] * 15)),
        "onpage_seo": clamp(100 - (metrics["missing_title"] * 10) - (metrics["missing_h1"] * 8) - (metrics["img_no_alt"] * 2)),
        "performance": psi_data.get("score", 60),
        "mobile_friendly": psi_mobile.get("score", 70),
        "security_https": clamp(100 if metrics["https_pages"] == total_pages else 50),
        # Stubs for later categories
        "competitor_gap": 75.0,  # placeholder
        "broken_links_health": clamp(100 - metrics["total_broken_links"] * 5),
        "roi_potential": clamp(50 + (100 - psi_data.get("score", 50)) * 0.8),
    }

    # ── 5. AI-Powered Executive Summary & Insights (Category A) ─────────────────
    prompt = f"""
    You are a professional SEO auditor.
    Website: {url}
    Overall health: {round(sum(category_scores.values()) / len(category_scores), 1)}%
    Key metrics:
    - Broken links: {metrics['total_broken_links']}
    - Missing titles: {metrics['missing_title']}
    - PageSpeed score: {psi_data.get('score', 'N/A')}
    - Mobile score: {psi_mobile.get('score', 'N/A')}

    Generate a structured executive summary:
    1. 150–200 word professional summary
    2. List 3–5 key strengths
    3. List 3–5 critical weaknesses
    4. Top 3 priority fixes
    Return in JSON format.
    """

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        ai_content = response.text.strip()

        # Attempt to parse as JSON (Gemini often outputs valid JSON when asked)
        import json
        try:
            ai_data = json.loads(ai_content)
        except:
            ai_data = {"summary": ai_content, "strengths": [], "weaknesses": [], "priorities": []}

        executive_summary = ai_data.get("summary", "Audit completed.")
        strengths = ai_data.get("strengths", ["Good crawlability"])
        weaknesses = ai_data.get("weaknesses", ["Missing metadata"])
        priorities = ai_data.get("priorities", ["Fix broken links"])

    except Exception as e:
        print(f"Gemini failed: {e}")
        executive_summary = f"AI audit for {url} completed. Grade pending detailed review."
        strengths, weaknesses, priorities = [], [], []

    # ── 6. Competitor Gap (G) - Basic Stub ──────────────────────────────────────
    competitor_scores = []
    if competitors:
        for comp_url in competitors[:3]:  # limit to avoid long runtime
            try:
                comp_result = await analyze(comp_url, [])  # recursive but shallow
                competitor_scores.append(comp_result["overall"]["score"])
            except:
                pass

    avg_comp_score = sum(competitor_scores) / len(competitor_scores) if competitor_scores else None

    # ── Final Return Structure ──────────────────────────────────────────────────
    return {
        "overall": {
            "score": round(sum(category_scores.values()) / len(category_scores), 2),
            "grade": to_grade(sum(category_scores.values()) / len(category_scores)),  # reuse your grader
        },
        "summary": {
            "executive_summary": executive_summary,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "priority_fixes": priorities,
        },
        "category_scores": category_scores,
        "metrics": metrics,
        "competitor_analysis": {
            "your_score": category_scores["crawlability"],
            "avg_competitor_score": avg_comp_score,
            "gap": round((avg_comp_score - category_scores["crawlability"]) if avg_comp_score else 0, 1),
        },
        "roi_forecast": {
            "traffic_growth_potential": f"+{round(100 - category_scores['performance'], 1)}% possible",
            "priority_roi": "High" if category_scores["performance"] < 70 else "Medium",
        }
    }
