import asyncio
import logging
from typing import Dict, Any, Callable
from app.audit.seo import SEOAnalyzer
from app.audit.performance import PerformanceAnalyzer
from app.audit.links import LinkAnalyzer
from app.audit.competitor_report import CompetitorAnalyzer
from app.audit.grader import Grader

logger = logging.getLogger("audit_engine")

class WebsiteAuditRunner:
    def __init__(self, url: str, max_pages: int = 50):
        self.url = url
        self.max_pages = max_pages

    async def run_audit(self, progress_callback: Callable[[Dict[str, Any]], Any]):
        """
        Runs the full suite of technical audits and streams progress.
        """
        try:
            # Step 1: SEO Analysis
            await progress_callback({"status": "🔍 Analyzing SEO & Structure...", "crawl_progress": 20})
            seo_results = await SEOAnalyzer(self.url).analyze()

            # Step 2: Performance (LCP) Check
            await progress_callback({"status": "⚡ Measuring Performance (LCP)...", "crawl_progress": 50})
            perf_results = await PerformanceAnalyzer(self.url).analyze()

            # Step 3: Link Integrity
            await progress_callback({"status": "🔗 Checking Link Integrity...", "crawl_progress": 70})
            link_results = await LinkAnalyzer(self.url).analyze()

            # Step 4: Competitor Benchmarking
            await progress_callback({"status": "📊 Benchmarking Competitors...", "crawl_progress": 90})
            comp_results = await CompetitorAnalyzer(self.url).analyze()

            # Step 5: Final Grade Calculation
            grader = Grader()
            final_grade, overall_score = grader.calculate(seo_results, perf_results, link_results)

            # FINAL PAYLOAD: Must match index.html variable names exactly
            final_payload = {
                "overall_score": overall_score,
                "grade": final_grade,
                "breakdown": {
                    "seo": seo_results.get("score", 0),
                    "performance": {
                        "lcp_ms": perf_results.get("lcp", 0) 
                    },
                    "competitors": {
                        "top_competitor_score": comp_results.get("score", 0)
                    },
                    "links": {
                        "internal_links_count": link_results.get("internal", 0),
                        "warning_links_count": link_results.get("warnings", 0),
                        "broken_internal_links": link_results.get("broken", 0)
                    }
                },
                "chart_data": {
                    "bar": {
                        "labels": ["SEO", "Performance", "Links", "AI Trust"],
                        "data": [
                            seo_results.get("score", 0),
                            max(0, 100 - (perf_results.get("lcp", 0) / 100)),
                            85, # Static or calculated link score
                            90  # AI Confidence constant
                        ]
                    },
                    "doughnut": {
                        "labels": ["Healthy", "Warning", "Broken"],
                        "data": [
                            link_results.get("internal", 0),
                            link_results.get("warnings", 0),
                            link_results.get("broken", 0)
                        ]
                    }
                },
                "finished": True
            }

            await progress_callback(final_payload)
            return final_payload

        except Exception as e:
            logger.error(f"Audit failed for {self.url}: {str(e)}")
            await progress_callback({"error": f"Audit failed: {str(e)}", "finished": True})
