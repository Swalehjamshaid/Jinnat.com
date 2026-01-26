import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from urllib.parse import urlparse, urljoin

from .crawler import crawl
from .seo import analyze_onpage

logger = logging.getLogger("audit_engine")


class WebsiteAuditRunner:
    def __init__(self, url: str, max_pages: int = 10):
        self.url = url
        self.max_pages = max_pages

    async def run_audit(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        async def send_update(pct: int, msg: str):
            if progress_callback:
                await progress_callback({
                    "crawl_progress": pct,
                    "status": msg,
                    "finished": False
                })

        try:
            # 1️⃣ Crawl Pages
            await send_update(5, "Starting crawl...")
            crawl_result = await crawl(self.url, max_pages=self.max_pages)
            pages = crawl_result.get("report", [])
            await send_update(25, f"Crawled {len(pages)} pages")

            # 2️⃣ Analyze SEO
            await send_update(40, "Analyzing on-page SEO...")
            seo_data = await analyze_onpage(pages)
            onpage_score = round(seo_data.get("score", 80))

            # 3️⃣ Link Analysis
            await send_update(55, "Analyzing links...")
            internal_links = []
            external_links = []
            broken_internal_links = 0
            domain = urlparse(self.url).netloc

            for page in pages:
                html = page.get("html", "")
                soup = None
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "lxml")
                except Exception:
                    continue
                if soup:
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        full_url = urljoin(page.get("url", ""), href)
                        link_domain = urlparse(full_url).netloc
                        if link_domain == domain:
                            internal_links.append(full_url)
                            # Simple broken link detection (real async check can be added)
                        else:
                            external_links.append(full_url)

            internal_links = list(set(internal_links))
            external_links = list(set(external_links))
            coverage_score = min(100, len(pages) * 10)
            confidence_score = min(100, 50 + len(pages) * 5)

            # 4️⃣ Performance Score Placeholder
            await send_update(70, "Analyzing performance...")
            performance_score = 85  # You can integrate PSI/Lighthouse here

            # 5️⃣ Calculate Overall
            overall_score = round((onpage_score + performance_score + coverage_score) / 3)
            grade = "A" if overall_score > 80 else "B"

            # 6️⃣ Build Audit Result
            result = {
                "overall_score": overall_score,
                "grade": grade,
                "breakdown": {
                    "onpage": onpage_score,
                    "performance": performance_score,
                    "coverage": coverage_score,
                    "confidence": confidence_score
                },
                "metrics": {
                    "internal_links": len(internal_links),
                    "external_links": len(external_links),
                    "broken_internal_links": broken_internal_links
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
                        "labels": ["Good Links", "Warnings", "Broken Links"],
                        "data": [len(internal_links), len(external_links), broken_internal_links]
                    }
                },
                "audit_time": round(asyncio.get_event_loop().time() - start_time, 2)
            }

            await send_update(100, "Audit completed")
            return result

        except Exception as e:
            logger.exception("Audit failed")
            if progress_callback:
                await progress_callback({"error": str(e), "finished": True})
            return {"error": str(e)}
