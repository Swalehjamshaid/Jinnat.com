# app/audit/psi.py
import aiohttp
import asyncio
from typing import Dict

PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

async def fetch_lighthouse(
    url: str, api_key: str, strategy: str = "mobile", timeout: int = 10
) -> Dict[str, float]:
    """
    Fetch Lighthouse/PageSpeed Insights data asynchronously.
    Returns defaults if API fails.
    """

    categories = ["performance", "seo", "accessibility", "best-practices"]
    params = [
        ("url", url),
        ("key", api_key),
        ("strategy", strategy),
    ] + [("category", c) for c in categories]

    # Retry with exponential backoff
    for attempt in range(1, 4):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(PAGESPEED_API, params=params, timeout=timeout) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    result = await resp.json()
                    categories_result = result.get("lighthouseResult", {}).get("categories", {})
                    audits = result.get("lighthouseResult", {}).get("audits", {})

                    return {
                        "performance": categories_result.get("performance", {}).get("score", 0) * 100,
                        "seo": categories_result.get("seo", {}).get("score", 0) * 100,
                        "accessibility": categories_result.get("accessibility", {}).get("score", 0) * 100,
                        "best_practices": categories_result.get("best-practices", {}).get("score", 0) * 100,
                        "lcp": audits.get("largest-contentful-paint", {}).get("numericValue", 0) / 1000,
                        "cls": audits.get("cumulative-layout-shift", {}).get("numericValue", 0),
                    }
        except asyncio.TimeoutError:
            print(f"[PSI] Attempt {attempt}/3 timed out for {url}")
        except Exception as e:
            print(f"[PSI] Attempt {attempt}/3 failed for {url}: {e}")

        # Exponential backoff
        await asyncio.sleep(1 * attempt)

    # Default values if all attempts fail
    print(f"[PSI] Failed to fetch Lighthouse metrics for {url}. Returning defaults.")
    return {
        "performance": 0,
        "seo": 0,
        "accessibility": 0,
        "best_practices": 0,
        "lcp": 0,
        "cls": 0,
    }
