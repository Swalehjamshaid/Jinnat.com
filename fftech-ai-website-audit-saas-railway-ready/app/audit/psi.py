# app/audit/psi.py
import requests
from typing import Dict, Optional
import logging
import time

logger = logging.getLogger("psi_fetcher")

PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
DEFAULT_TIMEOUT = 20
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries


def fetch_lighthouse(
    url: str,
    api_key: str,
    strategy: str = "mobile",
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
) -> Dict[str, float]:
    """
    Fetches Lighthouse/PageSpeed Insights metrics from Google API.

    Args:
        url (str): The URL of the website to audit.
        api_key (str): Google Pagespeed Insights API key.
        strategy (str, optional): 'mobile' or 'desktop'. Defaults to 'mobile'.
        timeout (int, optional): Request timeout in seconds. Defaults to 20.
        retries (int, optional): Number of retries for transient errors. Defaults to 3.

    Returns:
        Dict[str, float]: Dictionary containing:
            - performance, seo, accessibility, best_practices (0-100)
            - lcp (seconds)
            - cls (unitless)
    """
    params = {
        "url": url,
        "category": ["performance", "seo", "accessibility", "best-practices"],
        "key": api_key,
        "strategy": strategy,
    }

    attempt = 0
    while attempt < retries:
        try:
            response = requests.get(PAGESPEED_API, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()

            categories = data.get("lighthouseResult", {}).get("categories", {})
            audits = data.get("lighthouseResult", {}).get("audits", {})

            return {
                "performance": categories.get("performance", {}).get("score", 0) * 100,
                "seo": categories.get("seo", {}).get("score", 0) * 100,
                "accessibility": categories.get("accessibility", {}).get("score", 0) * 100,
                "best_practices": categories.get("best-practices", {}).get("score", 0) * 100,
                "lcp": audits.get("largest-contentful-paint", {}).get("numericValue", 0) / 1000,
                "cls": audits.get("cumulative-layout-shift", {}).get("numericValue", 0),
            }

        except requests.RequestException as e:
            attempt += 1
            logger.warning(f"[PSI] Request attempt {attempt}/{retries} failed: {e}")
            time.sleep(RETRY_DELAY)
        except KeyError as e:
            logger.error(f"[PSI] Key parsing error: {e}")
            break
        except Exception as e:
            logger.exception(f"[PSI] Unexpected error: {e}")
            break

    # Fallback if all attempts fail
    logger.error(f"[PSI] Failed to fetch Lighthouse metrics for {url}. Returning defaults.")
    return {
        "performance": 0.0,
        "seo": 0.0,
        "accessibility": 0.0,
        "best_practices": 0.0,
        "lcp": 0.0,
        "cls": 0.0,
    }
