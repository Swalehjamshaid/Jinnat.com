# app/audit/runner.py
import asyncio
import logging
from typing import Optional, Callable, Dict, Any

from .crawler import crawl
from .seo import analyze_onpage
from .links import analyze_links_async
from .performance import analyze_performance

logger = logging.getLogger("audit_engine")


class WebsiteAuditRunner:
    def __init__(self, url: str, psi_api_key: Optional[str] = None, max_pages: int = 10):
        self.url = url
        self.psi_api_key = psi_api_key
        self.max_pages = max_pages

    async def run_audit(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        def progress(pct, msg):
            if progress_callback:
                return progress_callback({
                    "crawl_progress": pct,
                    "status": msg,
                    "finished": False
                })

        # ── Crawl
        await progress(5, "Crawling website…")
        crawl_result = await crawl(self.url, max_pages=self.max_pages)

        pages = crawl_result.get("report", [])
        page_urls = [p["url"] for p in pages]

        # ── SEO
        await progress(25, "Analyzing on-page SEO…")
        seo = await analyze_onpage(pages)

        # ── Links
        await progress(45, "Analyzing link structure…")
        links = await analyze_links_async(pages, self.url)

        # ── Performance (parallel)
        await progress(65, "Measuring performance…")
        perf_tasks = [asyncio.to_thread(analyze_performance, u) for u in page_urls]
        perf_results = await asyncio.gather(*perf_tasks, return_exceptions=True)

        perf_scores = [
            r.get("score", 70) for r in perf_results if isinstance(r, dict)
        ]

        # ── Final scoring (WHAT FRONTEND NEEDS)
        onpage_score = round(seo.get("score", 80))
        performance_score = round(sum(perf_scores) / max(len(perf_scores), 1))
        coverage_score = min(100, round((links["internal"] / max(len(page_urls), 1)) * 10))
        confidence_score = round((onpage_score + performance_score + coverage_score) / 3)

        overall = round(
            onpage_score * 0.35 +
            performance_score * 0.35 +
            coverage_score * 0.2 +
            confidence_score * 0.1
        )

        grade = (
            "A+" if overall >= 90 else
            "A" if overall >= 80 else
            "B" if overall >= 70 else
            "C" if overall >= 60 else
            "D"
        )

        await progress(95, "Finalizing report…")

        return {
            "overall_score": overall,
            "grade": grade,
            "breakdown": {
                "onpage": onpage_score,
                "performance": performance_score,
                "coverage": coverage_score,
                "confidence": confidence_score
            },
            "metrics": {
                "internal_links": links["internal"],
                "external_links": links["external"],
                "broken_internal_links": links["broken_internal"]
            },
            "chart_data": {
                "bar": {
                    "labels": ["SEO", "Performance", "Coverage", "Confidence"],
                    "data": [onpage_score, performance_score, coverage_score, confidence_score]
                },
                "radar": {
                    "labels": ["SEO", "Performance", "Coverage", "Confidence"],
                    "data": [onpage_score, performance_score, coverage_score, confidence_score]
                },
                "doughnut": {
                    "labels": ["Good", "Warning", "Critical"],
                    "data": [links["internal"], links["external"], links["broken_internal"]]
                }
            },
            "audit_time": round(asyncio.get_event_loop().time() - start_time, 2)
        }
