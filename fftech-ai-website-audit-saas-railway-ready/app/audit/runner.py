import asyncio
import logging
from typing import Optional, Callable, Dict, Any

from .crawler import crawl
from .seo import analyze_onpage
from .grader import grade_website
from .links import analyze_links_async
from .record import fetch_site_html
from .psi import fetch_lighthouse
from .competitor_report import compare_with_competitors

logger = logging.getLogger("audit_engine")


class WebsiteAuditRunner:
    """Integrated runner for FFTech AI Website Audit"""

    def __init__(self, url: str, max_pages: int = 20, psi_api_key: Optional[str] = None):
        self.url = url
        self.max_pages = max_pages
        self.psi_api_key = psi_api_key

    async def run_audit(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        async def send_update(pct: float, msg: str):
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback({"crawl_progress": pct, "status": msg, "finished": False})
                else:
                    progress_callback({"crawl_progress": pct, "status": msg, "finished": False})

        # 1️⃣ Crawl pages
        await send_update(5, "Crawling internal pages…")
        crawl_result = await crawl(self.url, max_pages=self.max_pages)
        pages = crawl_result.get("report", [])

        # 2️⃣ Fetch raw HTML for links
        await send_update(15, "Fetching page HTML…")
        html_docs = await fetch_site_html(self.url, self.max_pages)

        # 3️⃣ SEO Analysis
        await send_update(30, "Analyzing SEO heuristics…")
        seo_data = await analyze_onpage(pages)
        onpage_score = round(seo_data.get("score", 80))

        # 4️⃣ Link Analysis
        await send_update(50, "Checking internal and external links…")
        links_data = await analyze_links_async(html_docs, self.url, progress_callback=progress_callback)

        # 5️⃣ Performance Metrics
        await send_update(70, "Fetching PageSpeed metrics…")
        psi_data: Dict[str, Any] = {}
        if self.psi_api_key:
            try:
                psi_data = await asyncio.to_thread(fetch_lighthouse, self.url, api_key=self.psi_api_key)
            except Exception as e:
                logger.warning(f"PSI fetch failed: {e}")

        # 6️⃣ Page Grading
        await send_update(80, "Grading pages…")
        graded_pages = [{"url": page.get("url", ""), "grade": grade_website(page.get("html", ""), page.get("url", ""))} for page in pages]

        # 7️⃣ Competitor Comparison
        await send_update(90, "Analyzing competitors…")
        competitor_data = await asyncio.to_thread(compare_with_competitors, self.url)
        top_score = competitor_data.get("top_competitor_score", 100)

        # 8️⃣ Aggregate final report
        lcp_ms = psi_data.get("lcp_ms", 0)
        link_score = min(links_data.get("internal_links_count", 0), 100)
        perf_score = min(100 - lcp_ms / 50, 100)

        overall_score = round((onpage_score + link_score + perf_score + 90) / 4)
        overall_score = min(overall_score, 100)

        grade = (
            "A+" if overall_score >= 90 else
            "A" if overall_score >= 80 else
            "B" if overall_score >= 70 else
            "C" if overall_score >= 60 else
            "D"
        )

        chart_data = {
            "bar": {
                "labels": ["SEO", "Links", "Perf", "AI"],
                "data": [onpage_score, link_score, perf_score, 90]
            },
            "radar": {
                "labels": ["SEO", "Links", "Perf", "AI"],
                "data": [onpage_score, link_score, perf_score, 90]
            },
            "doughnut": {
                "labels": ["Good", "Warning", "Broken"],
                "data": [
                    links_data.get("internal_links_count", 0),
                    links_data.get("warning_links_count", 0),
                    links_data.get("broken_internal_links", 0)
                ]
            }
        }

        await send_update(100, "Audit complete.")
        return {
            "overall_score": overall_score,
            "grade": grade,
            "pages_graded": graded_pages,
            "breakdown": {
                "seo": onpage_score,
                "links": links_data,
                "performance": psi_data,
                "competitors": competitor_data
            },
            "chart_data": chart_data,
            "audit_time": round(asyncio.get_event_loop().time() - start_time, 2)
        }
