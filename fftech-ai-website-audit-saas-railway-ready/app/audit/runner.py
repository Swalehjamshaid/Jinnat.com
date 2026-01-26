# app/audit/runner.py

import asyncio
import logging
from typing import Optional, Callable, Dict, Any, List
from urllib.parse import urlparse, urljoin

import aiohttp
from bs4 import BeautifulSoup

from .seo import analyze_onpage
from .links import analyze_links
from .performance import analyze_performance
from .psi import fetch_lighthouse

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)


class WebsiteAuditRunner:
    def __init__(self, url: str, psi_api_key: Optional[str] = None, max_pages: int = 10):
        self.url = url
        self.psi_api_key = psi_api_key
        self.max_pages = max_pages
        self.html_docs: Dict[str, str] = {}
        self.report: Dict[str, Any] = {}

    # -----------------------------
    # Async HTML fetch
    # -----------------------------
    async def fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        try:
            async with session.get(url, timeout=15, ssl=False) as resp:
                return await resp.text()
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return ""

    # -----------------------------
    # Async site crawler
    # -----------------------------
    async def crawl_site(self, progress_callback: Optional[Callable] = None) -> Dict[str, str]:
        visited = set()
        to_visit = {self.url}
        html_docs: Dict[str, str] = {}

        async with aiohttp.ClientSession() as session:
            while to_visit and len(visited) < self.max_pages:
                tasks = [self.fetch_html(session, url) for url in to_visit]
                results = await asyncio.gather(*tasks)
                current_urls = list(to_visit)
                to_visit.clear()

                for url, html in zip(current_urls, results):
                    if url in visited or not html:
                        continue
                    html_docs[url] = html
                    visited.add(url)

                    soup = BeautifulSoup(html, 'lxml')
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        joined_url = urljoin(url, href)
                        if urlparse(joined_url).netloc == urlparse(self.url).netloc:
                            if joined_url not in visited:
                                to_visit.add(joined_url)

                    if progress_callback:
                        await progress_callback({
                            "status": f"Crawled {len(visited)} pages...",
                            "crawl_progress": round(len(visited)/self.max_pages*100, 2),
                            "finished": False
                        })

        return html_docs

    # -----------------------------
    # Run full audit
    # -----------------------------
    async def run_audit(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        logger.info(f"Starting audit for {self.url}")

        # 1️⃣ Crawl site
        if progress_callback:
            await progress_callback({"status": "Starting site crawl...", "crawl_progress": 0, "finished": False})
        self.html_docs = await self.crawl_site(progress_callback)

        # 2️⃣ On-page SEO analysis (concurrent)
        if progress_callback:
            await progress_callback({"status": "Analyzing SEO...", "crawl_progress": 20, "finished": False})
        seo_task = asyncio.to_thread(analyze_onpage, self.html_docs)

        # 3️⃣ Link analysis
        links_task = asyncio.to_thread(analyze_links, self.html_docs)

        # 4️⃣ Performance metrics (parallel per page)
        perf_tasks = [asyncio.to_thread(analyze_performance, url) for url in self.html_docs.keys()]

        # 5️⃣ PSI metrics if API key provided
        psi_tasks: List[asyncio.Future] = []
        if self.psi_api_key:
            psi_tasks = [asyncio.to_thread(fetch_lighthouse, url, self.psi_api_key) for url in self.html_docs.keys()]

        # Gather all tasks concurrently
        seo_metrics, links_metrics, perf_results, psi_results = await asyncio.gather(
            seo_task,
            links_task,
            asyncio.gather(*perf_tasks),
            asyncio.gather(*psi_tasks) if psi_tasks else asyncio.sleep(0)
        )

        # Map perf and psi results to URLs
        perf_metrics = dict(zip(self.html_docs.keys(), perf_results))
        psi_metrics = dict(zip(self.html_docs.keys(), psi_results)) if psi_tasks else {}

        # 6️⃣ Compile final report
        self.report = {
            "url": self.url,
            "pages": list(self.html_docs.keys()),
            "seo": seo_metrics,
            "links": links_metrics,
            "performance": perf_metrics,
            "psi": psi_metrics
        }

        if progress_callback:
            await progress_callback({"status": "Audit complete!", "crawl_progress": 100, "finished": True})

        logger.info(f"Audit finished for {self.url}")
        return self.report


# -----------------------------
# Quick runner example
# -----------------------------
if __name__ == "__main__":
    import json

    async def progress_cb(data):
        print(f"[{data.get('crawl_progress', 0)}%] {data.get('status')}")

    url_to_audit = "https://example.com"
    psi_key = "YOUR_PSI_API_KEY"

    runner = WebsiteAuditRunner(url_to_audit, psi_api_key=psi_key, max_pages=5)
    report = asyncio.run(runner.run_audit(progress_callback=progress_cb))

    with open("audit_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("Audit completed! Report saved as audit_report.json")
