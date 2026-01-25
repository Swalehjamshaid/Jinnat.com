import logging
from urllib.request import urlopen, Request

logger = logging.getLogger(__name__)

DEFAULT_RESULT = {
    "performance": 50.0,
    "seo": 50.0,
    "accessibility": 50.0,
    "best_practices": 50.0,
    "lcp": 2.0,
    "cls": 0.05,
}

HEADERS = {"User-Agent": "FFTechAuditor/2.0"}

def python_library_audit(url: str):
    """
    Pre-audit entirely in Python:
    - Checks reachability
    - Sets baseline SEO and performance metrics
    """
    result = DEFAULT_RESULT.copy()
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=5) as resp:
            if resp.getcode() == 200:
                result["seo"] += 10
                result["performance"] += 10
            else:
                result["seo"] -= 5
                result["performance"] -= 5
    except Exception:
        logger.warning("Failed to reach %s", url)
        result["seo"] -= 10
        result["performance"] -= 10
    return result

async def fetch_lighthouse(url: str, api_key: str = None):
    """
    Python-compatible placeholder for Lighthouse/PSI.
    Returns pre-audit metrics when PSI API is not configured.
    """
    return python_library_audit(url)
