# app/audit/runner.py
import requests
import httpx
import certifi
from bs4 import BeautifulSoup
import logging
import time
from typing import Dict

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)

# --- Global session for requests with SSL verification ---
session = requests.Session()
session.verify = certifi.where()

# Optional: httpx client for async requests (if ever needed)
httpx_client = httpx.Client(verify=certifi.where())

# --- Core Audit Function ---
def run_audit(url: str) -> Dict:
    """
    Perform a synchronous audit of the given URL.
    Returns a dictionary with:
        - overall_score
        - grade
        - breakdown: onpage, performance, coverage, confidence
        - excel_path (optional)
        - pptx_path (optional)
    """
    logger.info("Starting audit for URL: %s", url)
    
    result = {
        "overall_score": 0,
        "grade": "F",
        "breakdown": {
            "onpage": 0,
            "performance": 0,
            "coverage": 0,
            "confidence": 0
        },
        "excel_path": None,
        "pptx_path": None
    }

    try:
        # --- Step 1: Fetch main page ---
        logger.info("Fetching main page...")
        response = session.get(url, timeout=15)
        response.raise_for_status()  # raise error if non-200
        html = response.text

        # --- Step 2: Parse page ---
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.title.string if soup.title else ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        meta_desc_content = meta_desc["content"] if meta_desc else ""

        # --- Step 3: Simple SEO audit ---
        seo_score = 0
        if title_tag and len(title_tag.strip()) > 0:
            seo_score += 30
        if meta_desc_content and len(meta_desc_content.strip()) > 0:
            seo_score += 20

        # --- Step 4: Link audit ---
        links = soup.find_all("a", href=True)
        total_links = len(links)
        broken_links = 0
        for link in links[:50]:  # limit to first 50 to save time
            try:
                resp = session.head(link["href"], allow_redirects=True, timeout=5)
                if resp.status_code >= 400:
                    broken_links += 1
            except requests.RequestException:
                broken_links += 1
        coverage_score = max(0, 100 - int((broken_links / max(total_links,1)) * 100))

        # --- Step 5: Performance placeholder ---
        # Here you could add real performance metrics, e.g., page size, load time
        perf_score = max(50, min(100, 100 - len(html)//1000))  # rough estimate

        # --- Step 6: AI Confidence placeholder ---
        confidence_score = 90  # Example static confidence

        # --- Step 7: Calculate overall score & grade ---
        overall_score = int((seo_score * 0.4) + (perf_score * 0.3) + (coverage_score * 0.2) + (confidence_score * 0.1))
        grade = "A" if overall_score >= 85 else "B" if overall_score >= 70 else "C" if overall_score >= 55 else "D" if overall_score >= 40 else "F"

        # --- Step 8: Populate result ---
        result.update({
            "overall_score": overall_score,
            "grade": grade,
            "breakdown": {
                "onpage": seo_score,
                "performance": perf_score,
                "coverage": coverage_score,
                "confidence": confidence_score
            },
            # These can be real generated file paths if you implement Excel/PPTX generation
            "excel_path": f"/static/reports/{overall_score}_report.xlsx",
            "pptx_path": f"/static/reports/{overall_score}_report.pptx"
        })

        logger.info("Audit completed: %s", result)

    except requests.RequestException as e:
        logger.exception("HTTP request failed for %s", url)
        raise RuntimeError(f"Failed to fetch URL: {e}")

    except Exception as e:
        logger.exception("Audit processing failed for %s", url)
        raise RuntimeError(f"Audit error: {e}")

    return result
