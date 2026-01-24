
# app/audit/runner.py
import os
import asyncio
from typing import Any, Dict, Tuple

from app.audit.psi import async_fetch_psi

# If you have your own crawler, import it. Stub provided here:
async def crawl_site(url: str, max_pages: int = 3, timeout_total_s: int = 20) -> Dict[str, Any]:
    # TODO: plug your real crawler here. The stub simulates work.
    await asyncio.sleep(1.2)  # simulate fetch/parse
    return {
        "pages": 3,
        "onpage": 85,
        "coverage": 80
    }

async def run_audit(url: str) -> Dict[str, Any]:
    """
    Run the full audit concurrently (PSI + crawl) with robust error handling.
    """
    psi_api_key = os.getenv("PSI_API_KEY")

    psi_coro = async_fetch_psi(url=url, strategy="mobile", api_key=psi_api_key, timeout_read_s=15.0, retries=1)
    crawl_coro = crawl_site(url=url, max_pages=3, timeout_total_s=20)

    psi_data, crawl_result = await asyncio.gather(psi_coro, crawl_coro, return_exceptions=True)

    # Default breakdown
    onpage = 0
    performance = 0
    coverage = 0
    confidence = 70

    # Extract from crawler
    if not isinstance(crawl_result, Exception) and isinstance(crawl_result, dict):
        onpage = int(crawl_result.get("onpage", 0))
        coverage = int(crawl_result.get("coverage", 0))

    # Extract from PSI (if available)
    if not isinstance(psi_data, Exception) and isinstance(psi_data, dict):
        try:
            # Lighthouse performance score: 0..1 → convert to 0..100
            perf_score = psi_data["lighthouseResult"]["categories"]["performance"]["score"]
            performance = int(round((perf_score or 0) * 100))
        except Exception:
            performance = 0

    # Compute overall (simple weighted)
    # Adjust weights as you wish
    overall = int(round(0.4 * onpage + 0.4 * performance + 0.2 * coverage))

    # Map to grade
    def to_grade(score: int) -> str:
        if score >= 90: return "A"
        if score >= 80: return "B+"
        if score >= 70: return "B"
        if score >= 60: return "C"
        if score >= 50: return "D"
        return "F"

    result = {
        "overall_score": overall,
        "grade": to_grade(overall),
        "breakdown": {
            "onpage": onpage,
            "performance": performance,
            "coverage": coverage,
            "confidence": confidence
        },
        "finished": True,
        "crawl_progress": 1.0
    }

    # Attach debug info if any branch failed (optional for your logs)
    if isinstance(psi_data, Exception):
        result["psi_error"] = str(psi_data)
    if isinstance(crawl_result, Exception):
        result["crawl_error"] = str(crawl_result)

    return result
