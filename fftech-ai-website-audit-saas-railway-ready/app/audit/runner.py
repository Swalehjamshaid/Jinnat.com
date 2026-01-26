# app/audit/runner.py
import asyncio
import logging
from typing import Optional, Callable, Dict, Any

from .crawler import crawl
from .seo import analyze_onpage
from .links import analyze_links_async
from .performance import analyze_performance
from .record import fetch_site_html
from .psi import fetch_lighthouse

logger = logging.getLogger("audit_engine")

class WebsiteAuditRunner:
    def __init__(self, url: str, psi_api_key: Optional[str] = None, max_pages: int = 50):
        self.url = url
        self.psi_api_key = psi_api_key
        self.max_pages = max_pages
        self.html_docs: Dict[str, Any] = {}
        self.report: Dict[str, Any] = {}

    async def run_audit(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Run the full audit asynchronously with real-time progress updates.
        """
        start_time = asyncio.get_event_loop().time()

        # 1. Crawl site
        if progress_callback:
            await progress_callback({"status": "Starting site crawl...", "crawl_progress": 0, "finished": False})

        logger.info(f"Starting crawl for {self.url}")
        crawl_result = await crawl(self.url, max_pages=self.max_pages)

        self.html_docs = {r["url"]: r.get("seo", {}) for r in crawl_result.get("report", [])}

        if progress_callback:
            await progress_callback({"status": "Crawl complete → fetching full HTML...", "crawl_progress": 30, "finished": False})

        # 2. Fetch full HTML (sync → run in thread pool)
        self.html_docs = await asyncio.to_thread(fetch_site_html, self.url, max_pages=self.max_pages)

        # 3. On-page SEO
        seo_metrics = await analyze_onpage(self.html_docs, progress_callback=progress_callback)

        # 4. Link analysis
        links_metrics = await analyze_links_async(self.html_docs, self.url, progress_callback=progress_callback)

        # 5. Performance analysis – parallelized
        perf_metrics = {}
        perf_tasks = [
            asyncio.to_thread(analyze_performance, page_url)
            for page_url in self.html_docs.keys()
        ]
        perf_results = await asyncio.gather(*perf_tasks, return_exceptions=True)

        for page_url, result in zip(self.html_docs.keys(), perf_results):
            perf_metrics[page_url] = {} if isinstance(result, Exception) else result

            if progress_callback:
                done = len(perf_metrics)
                total = len(self.html_docs)
                pct = round(done / total * 30 + 40, 1)  # 40–70% range
                await progress_callback({
                    "crawl_progress": pct,
                    "status": f"Performance analyzed: {done}/{total} pages",
                    "finished": False
                })

        # 6. PSI / Lighthouse – parallelized if key exists
        psi_metrics = {}
        if self.psi_api_key:
            psi_tasks = [
                asyncio.to_thread(fetch_lighthouse, page_url, self.psi_api_key)
                for page_url in self.html_docs.keys()
            ]
            psi_results = await asyncio.gather(*psi_tasks, return_exceptions=True)

            for page_url, result in zip(self.html_docs.keys(), psi_results):
                psi_metrics[page_url] = {} if isinstance(result, Exception) else result

                if progress_callback:
                    done = len(psi_metrics)
                    total = len(self.html_docs)
                    pct = round(done / total * 30 + 70, 1)  # 70–100% range
                    await progress_callback({
                        "crawl_progress": pct,
                        "status": f"PageSpeed Insights: {done}/{total} pages",
                        "finished": False
                    })

        # 7. Final report
        self.report = {
            "url": self.url,
            "crawl": crawl_result,
            "seo": seo_metrics,
            "links": links_metrics,
            "performance": perf_metrics,
            "psi": psi_metrics,
            "audit_duration_seconds": round(asyncio.get_event_loop().time() - start_time, 2),
        }

        if progress_callback:
            await progress_callback({"status": "Audit completed successfully!", "crawl_progress": 100, "finished": True})

        return self.report
