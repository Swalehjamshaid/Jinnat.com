# app/audit/psi.py
import requests
from typing import Dict

PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

def fetch_lighthouse(url: str, api_key: str, strategy: str = "mobile") -> Dict[str, float]:
    """
    Fetches Lighthouse/PageSpeed Insights data from Google API.

    Returns:
        Dict with keys:
        - performance, seo, accessibility, best_practices: 0-100 score
        - lcp: Largest Contentful Paint in seconds
        - cls: Cumulative Layout Shift
    """
    try:
        params = {
            "url": url,
            "category": ["performance", "seo", "accessibility", "best-practices"],
            "key": api_key,
            "strategy": strategy,  # 'mobile' or 'desktop'
        }

        r = requests.get(PAGESPEED_API, params=params, timeout=20)
        r.raise_for_status()
        result = r.json()

        categories = result["lighthouseResult"]["categories"]
        audits = result["lighthouseResult"]["audits"]

        return {
            "performance": categories.get("performance", {}).get("score", 0) * 100,
            "seo": categories.get("seo", {}).get("score", 0) * 100,
            "accessibility": categories.get("accessibility", {}).get("score", 0) * 100,
            "best_practices": categories.get("best-practices", {}).get("score", 0) * 100,
            "lcp": audits.get("largest-contentful-paint", {}).get("numericValue", 0) / 1000,
            "cls": audits.get("cumulative-layout-shift", {}).get("numericValue", 0),
        }

    except requests.RequestException as e:
        print(f"[PSI] Request Error: {e}")
    except KeyError as e:
        print(f"[PSI] Key Error: {e}")

    # Return defaults if API fails
    return {
        "performance": 0,
        "seo": 0,
        "accessibility": 0,
        "best_practices": 0,
        "lcp": 0,
        "cls": 0,
    }
