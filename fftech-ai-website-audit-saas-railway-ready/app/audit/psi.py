# app/audit/psi.py
import requests
from typing import Dict

PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

def fetch_lighthouse(url: str, api_key: str, strategy: str = "mobile") -> Dict[str, float]:
    """
    Fetch Lighthouse/PageSpeed Insights data from Google API.
    Returns 0 if API fails.
    """
    try:
        # Build categories as multiple params
        categories = ["performance", "seo", "accessibility", "best-practices"]
        params = [
            ("url", url),
            ("key", api_key),
            ("strategy", strategy),
        ] + [("category", c) for c in categories]

        # Retry 3 times for network issues
        for attempt in range(1, 4):
            try:
                r = requests.get(PAGESPEED_API, params=params, timeout=30)
                r.raise_for_status()
                break
            except requests.RequestException as e:
                print(f"[PSI] Request attempt {attempt}/3 failed: {e}")
                if attempt == 3:
                    raise
        else:
            raise Exception("Failed to fetch Lighthouse metrics after 3 attempts")

        result = r.json()
        categories_result = result["lighthouseResult"]["categories"]
        audits = result["lighthouseResult"]["audits"]

        return {
            "performance": categories_result.get("performance", {}).get("score", 0) * 100,
            "seo": categories_result.get("seo", {}).get("score", 0) * 100,
            "accessibility": categories_result.get("accessibility", {}).get("score", 0) * 100,
            "best_practices": categories_result.get("best-practices", {}).get("score", 0) * 100,
            "lcp": audits.get("largest-contentful-paint", {}).get("numericValue", 0) / 1000,
            "cls": audits.get("cumulative-layout-shift", {}).get("numericValue", 0),
        }

    except Exception as e:
        print(f"[PSI] Failed to fetch Lighthouse metrics for {url}. Returning defaults. Error: {e}")
        return {
            "performance": 0,
            "seo": 0,
            "accessibility": 0,
            "best_practices": 0,
            "lcp": 0,
            "cls": 0,
        }
