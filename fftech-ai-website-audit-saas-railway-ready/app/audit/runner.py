# app/audit/runner.py
import logging
from typing import Any, Dict, Callable
from .crawler import crawl

logger = logging.getLogger("audit_engine")

class WebsiteAuditRunner:
    """Handles crawling, metrics aggregation, and streaming results."""

    def __init__(self, url: str, max_pages: int = 50, psi_api_key: str = None):
        self.url = url
        self.max_pages = max_pages
        self.psi_api_key = psi_api_key
        self.results = []

    async def run_audit(self, progress_callback: Callable[[Dict[str, Any]], Any] = None) -> Dict[str, Any]:
        """Run website audit and optionally stream progress."""
        try:
            logger.info(f"Starting audit for {self.url}")
            crawl_data = await crawl(self.url, max_pages=self.max_pages)
            self.results = crawl_data.get("report", [])

            # Aggregate link counts
            total_internal = sum(page["internal_links_count"] for page in self.results)
            total_external = sum(page["external_links_count"] for page in self.results)
            total_broken = sum(page["broken_internal_links"] for page in self.results)

            # Placeholder metrics
            lcp_values = [page["lcp_ms"] for page in self.results if page["lcp_ms"] is not None]
            avg_lcp = round(sum(lcp_values)/len(lcp_values), 2) if lcp_values else 0
            seo_scores = [80 for _ in self.results]  # placeholder
            overall_seo = round(sum(seo_scores)/len(seo_scores)) if seo_scores else 0
            competitor_scores = [page.get("top_competitor_score") or 0 for page in self.results]
            top_competitor_score = max(competitor_scores) if competitor_scores else 0

            chart_data = {
                "bar": {
                    "labels": ["SEO", "Perf (LCP)", "Competitors", "AI Confidence"],
                    "data": [overall_seo, avg_lcp, top_competitor_score, 90]
                },
                "radar": {
                    "labels": ["SEO", "Performance", "Links", "Competitors"],
                    "data": [overall_seo, avg_lcp, total_internal, top_competitor_score]
                }
            }

            if progress_callback:
                await progress_callback({"status": "Processing metrics...", "crawl_progress": 90})

            result = {
                "overall_score": round(sum(chart_data["bar"]["data"])/len(chart_data["bar"]["data"])),
                "grade": self.compute_grade(sum(chart_data["bar"]["data"])/len(chart_data["bar"]["data"])),
                "breakdown": {
                    "links": {
                        "internal_links_count": total_internal,
                        "external_links_count": total_external,
                        "broken_internal_links": total_broken
                    },
                    "performance": {"lcp_ms": avg_lcp},
                    "seo": overall_seo,
                    "competitors": {"top_competitor_score": top_competitor_score}
                },
                "chart_data": chart_data
            }

            if progress_callback:
                await progress_callback({"status": "Audit complete ✔", "crawl_progress": 100, "finished": True, **result})

            return result

        except Exception as e:
            logger.exception("Audit failed")
            raise e

    def compute_grade(self, score: float) -> str:
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        else:
            return "D"
