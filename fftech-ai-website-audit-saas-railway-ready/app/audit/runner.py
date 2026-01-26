
# app/audit/runner.py

import logging
from typing import Callable, Optional, Dict

from app.audit.crawler import async_crawl

logger = logging.getLogger("audit_engine")


async def run_audit(
    url: str,
    progress_callback: Optional[Callable] = None
) -> Dict:
    """
    Run the full async audit and return final structured report.
    """

    result = await async_crawl(url, max_pages=20, progress_callback=progress_callback)

    # Aggregate SEO
    total_img = sum(r["seo"]["images_missing_alt"] for r in result["report"])
    total_title = sum(r["seo"]["title_missing"] for r in result["report"])
    total_meta = sum(r["seo"]["meta_description_missing"] for r in result["report"])

    onpage = max(0, 100 - (total_img * 2 + total_title * 3 + total_meta * 2))
    performance = max(0, 100 - len(result["broken_internal"]) * 2)
    coverage = max(0, 100 - len(result["broken_external"]) * 1)

    confidence = int((onpage + performance + coverage) / 3)
    overall = int((onpage + performance + coverage + confidence) / 4)

    grade = (
        "A" if overall > 85 else
        "B" if overall > 70 else
        "C" if overall > 50 else
        "D"
    )

    return {
        "url": url,
        "overall_score": overall,
        "grade": grade,
        "breakdown": {
            "onpage": onpage,
            "performance": performance,
            "coverage": coverage,
            "confidence": confidence,
        },
        "chart_data": {
            "bar": {
                "labels": ["On‑page SEO", "Performance", "Coverage", "AI Confidence"],
                "data": [onpage, performance, coverage, confidence],
                "colors": ["#2563eb", "#059669", "#d97706", "#dc2626"]
            },
            "radar": {
                "labels": ["Images Alt Missing", "Title Missing", "Meta Missing",
                           "Internal Links", "External Links"],
                "data": [total_img, total_title, total_meta,
                         result["unique_internal"], result["unique_external"]]
            },
            "doughnut": {
                "labels": ["Broken Internal", "Broken External"],
                "data": [len(result["broken_internal"]), len(result["broken_external"])],
                "colors": ["#dc2626", "#d97706"]
            }
        },
        "report": result["report"],
        "metrics": {
            "internal_links": result["unique_internal"],
            "external_links": result["unique_external"],
            "broken_internal_links": len(result["broken_internal"]),
            "broken_external_links": len(result["broken_external"])
        }
    }
