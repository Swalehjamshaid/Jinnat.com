# app/audit/runner.py

import asyncio
import logging
from typing import Optional, Callable, Dict, Any

from .crawler import async_crawl
from .seo import analyze_onpage
from .links import analyze_links_async  # ✅ Correct function import
from .performance import analyze_performance
from .record import fetch_site_html
from .psi import fetch_lighthouse

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)


class WebsiteAuditRunner:
    """
    Asynchronous Website Audit Runner
    Can crawl a site, analyze SEO, links, performance, and optionally fetch PageSpeed Insights (PSI)
    """

    def __init__(self, url: str, psi_api_key: Optional[str] = None):
        self.url = url
        self.psi_api_key = psi_api_key
        self.html_docs: Dict[str, Any] = {}
        self.report: Dict[str, Any] = {}

    async def run_audit(
        self, progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Run the full audit asynchronously with real-time progress updates
        """

        # 1️⃣ Crawl the site asynchronously
        if progress_callback:
            await progress_callback({"status": "Starting site crawl...", "crawl_progress": 0, "finished": False})
        logger.info(f"Starting crawl for {self.url}")

        crawl_result = await async_crawl(self.url, progress_callback=progress_callback)
        self.html_docs = {r["url"]: r.get("seo", {}) for r in crawl_result.get("report", [])}

        if progress_callback:
            await progress_callback({"status": "Crawl complete, fetching HTML...", "crawl_progress": 0, "finished": False})

        # 2️⃣ Fetch full HTML for in-depth analysis
        self.html_docs = fetch_site_html(self.url, max_pages=50)

        # 3️⃣ On-page SEO Analysis
        seo_metrics = await analyze_onpage(self.html_docs, progress_callback=progress_callback)

        # 4️⃣ Link Analysis (internal, external, broken)
        links_metrics = await analyze_links_async(self.html_docs, self.url, progress_callback=progress_callback)

        # 5️⃣ Performance Analysis
        perf_metrics = {}
        for i, page_url in enumerate(self.html_docs.keys(), start=1):
            perf_metrics[page_url] = analyze_performance(page_url)
            if progress_callback:
                await progress_callback({
                    "crawl_progress": round(i / len(self.html_docs) * 100, 2),
                    "status": f"Performance analyzed for {i}/{len(self.html_docs)} pages...",
                    "finished": False
                })

        # 6️⃣ Optional PSI / Lighthouse metrics
        psi_metrics = {}
        if self.psi_api_key:
            for i, page_url in enumerate(self.html_docs.keys(), start=1):
                psi_metrics[page_url] = fetch_lighthouse(page_url, self.psi_api_key)
                if progress_callback:
                    await progress_callback({
                        "crawl_progress": round(i / len(self.html_docs) * 100, 2),
                        "status": f"PageSpeed Insights fetched for {i}/{len(self.html_docs)} pages...",
                        "finished": False
                    })

        # 7️⃣ Compile final report
        self.report = {
            "url": self.url,
            "crawl": crawl_result,
            "seo": seo_metrics,
            "links": links_metrics,
            "performance": perf_metrics,
            "psi": psi_metrics,
        }

        if progress_callback:
            await progress_callback({"status": "Audit complete!", "crawl_progress": 100, "finished": True})

        return self.report


# -------------------------------
# Convenience function for external use
# -------------------------------
async def run_audit(url: str, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    External helper function for FastAPI WebSocket or scripts
    """
    runner = WebsiteAuditRunner(url)
    return await runner.run_audit(progress_callback=progress_callback)
