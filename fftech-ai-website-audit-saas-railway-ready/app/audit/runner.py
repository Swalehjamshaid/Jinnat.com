import asyncio
import logging
from typing import Optional, Callable, Dict, Any

from .crawler import crawl
from .seo import analyze_onpage
# Assume these exist or point to your logic
# from .links import analyze_links_async 

logger = logging.getLogger("audit_engine")

class WebsiteAuditRunner:
    def __init__(self, url: str, psi_api_key: Optional[str] = None, max_pages: int = 10):
        self.url = url
        self.max_pages = max_pages

    async def run_audit(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        async def send_update(pct, msg):
            if progress_callback:
                await progress_callback({
                    "crawl_progress": pct,
                    "status": msg,
                    "finished": False
                })

        # 1. Crawl
        await send_update(10, "Crawling internal pages...")
        crawl_result = await crawl(self.url, max_pages=self.max_pages)
        pages = crawl_result.get("report", [])

        # 2. SEO (Fixed the list error here)
        await send_update(40, "Analyzing SEO Heuristics...")
        seo_data = await analyze_onpage(pages)

        # 3. Final Scoring Logic
        onpage_score = round(seo_data.get("score", 80))
        performance_score = 85  # Placeholder or call your performance module
        coverage_score = min(100, len(pages) * 10)
        confidence_score = 90

        overall = round((onpage_score + performance_score + coverage_score) / 3)

        return {
            "overall_score": overall,
            "grade": "A" if overall > 80 else "B",
            "breakdown": {
                "onpage": onpage_score,
                "performance": performance_score,
                "coverage": coverage_score,
                "confidence": confidence_score
            },
            "metrics": {
                "internal_links": len(pages),
                "external_links": 5,
                "broken_internal_links": 0
            },
            "chart_data": {
                "bar": {"labels": ["SEO", "Perf", "Links", "AI"], "data": [onpage_score, performance_score, coverage_score, confidence_score]},
                "radar": {"labels": ["SEO", "Perf", "Links", "AI"], "data": [onpage_score, performance_score, coverage_score, confidence_score]},
                "doughnut": {"labels": ["Good", "Warning", "Broken"], "data": [len(pages), 2, 0]}
            },
            "audit_time": round(asyncio.get_event_loop().time() - start_time, 2)
        }
