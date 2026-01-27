import asyncio
import logging
from typing import Optional, Callable, Dict, Any, List, Union
from urllib.parse import urlparse

from .crawler import crawl
from .seo import analyze_onpage
from .grader import grade_website
from .links import analyze_links_async
from .record import fetch_site_html
from .psi import fetch_lighthouse
from .competitor_report import compare_with_competitors

logger = logging.getLogger("audit_engine")

# Helper: Direct browser-like fetch fallback
try:
    import httpx
except ImportError:
    httpx = None

async def _direct_fetch_html(url: str) -> List[Dict[str, str]]:
    if httpx is None:
        logger.warning("httpx not installed; skipping direct fetch")
        return []
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text or ""
            if text.strip():
                return [{"url": str(resp.url), "html": text}]
    except Exception as e:
        logger.warning(f"Direct fetch failed for {url}: {e}")
    return []

class WebsiteAuditRunner:
    """
    Integrated runner for FF Tech AI Website Audit v4.2.
    Crawls, analyzes SEO, links, performance, competitors, and grades.
    """

    def __init__(self, url: str, max_pages: int = 20, psi_api_key: Optional[str] = None):
        if not url.startswith(("http://", "https://")):
            url = "https://" + url.lstrip("/")
        self.url = url
        self.max_pages = max_pages
        self.psi_api_key = psi_api_key

    async def run_audit(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        async def send_update(pct: float, msg: str, finished: bool = False):
            if progress_callback:
                payload = {"crawl_progress": pct, "status": msg, "finished": finished}
                try:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(payload)
                    else:
                        progress_callback(payload)
                except Exception:
                    pass  # Don't crash on callback failure

        await send_update(5, "Crawling internal pages…")

        # 1. Crawl
        try:
            crawl_result = await crawl(self.url, max_pages=self.max_pages)
            pages: List[Dict[str, Any]] = crawl_result.get("report", []) or []
        except Exception as e:
            logger.exception("Crawler failed")
            pages = []

        # 2. Fetch HTML (multi-page)
        await send_update(15, "Fetching page HTML…")
        try:
            # FIX: Properly await the thread execution to get a List, not a coroutine
            html_docs = await asyncio.to_thread(fetch_site_html, self.url, self.max_pages)
            if not isinstance(html_docs, list):
                html_docs = []
        except Exception as e:
            logger.exception("fetch_site_html failed")
            html_docs = []

        # Fallback: direct homepage fetch if nothing useful
        has_html = any(bool(p.get("html")) for p in pages)
        if not html_docs and not has_html:
            await send_update(22, "Direct fetching homepage…")
            html_docs = await _direct_fetch_html(self.url)

        # Unified pages for analysis
        pages_for_analysis: List[Dict[str, Any]] = pages
        if not pages or not has_html:
            if html_docs:
                pages_for_analysis = [
                    {"url": d.get("url", self.url), "html": d.get("html", "")}
                    for d in html_docs[:self.max_pages]
                ]
                logger.info("Using fallback HTML for analysis")
            else:
                pages_for_analysis = [{"url": self.url, "html": ""}]
                logger.warning("No HTML content available")

        # 3. SEO
        await send_update(30, "Analyzing on-page SEO…")
        try:
            seo_data = await analyze_onpage(pages_for_analysis)
            onpage_score = round(seo_data.get("score", 0))
        except Exception as e:
            logger.exception("SEO analysis failed")
            onpage_score = 0

        # 4. Links
        await send_update(50, "Analyzing links…")
        try:
            links_data_raw = await analyze_links_async(pages_for_analysis, self.url, progress_callback)
            links_data = {
                "internal_links_count": int(links_data_raw.get("internal_links_count", 0)),
                "external_links_count": int(links_data_raw.get("external_links_count", 0)),
                "broken_internal_links": int(links_data_raw.get("broken_internal_links", 0)),
                "warning_links_count": int(links_data_raw.get("warning_links_count", 0)),
            }
        except Exception as e:
            logger.exception("Link analysis failed")
            links_data = {"internal_links_count": 0, "external_links_count": 0, "broken_internal_links": 0, "warning_links_count": 0}

        # 5. Performance (PageSpeed)
        await send_update(70, "Fetching Core Web Vitals…")
        psi_data = {"lcp_ms": 0, "cls": 0}
        if self.psi_api_key:
            try:
                psi_data = await asyncio.to_thread(fetch_lighthouse, self.url, api_key=self.psi_api_key)
            except Exception as e:
                logger.warning(f"PSI failed: {e}")
        
        lcp_ms = float(psi_data.get("lcp_ms", 0) or 0.0)
        cls = float(psi_data.get("cls", 0) or 0.0)

        # 6. Per-page grading
        await send_update(80, "Grading pages…")
        graded_pages = []
        for page in pages_for_analysis:
            html = page.get("html", "") or ""
            page_url = page.get("url", self.url)
            try:
                grade = grade_website(html, page_url)
            except Exception:
                grade = "D"
            graded_pages.append({"url": page_url, "grade": grade})

        # 7. Competitors
        await send_update(90, "Comparing competitors…")
        try:
            competitor_data = await asyncio.to_thread(compare_with_competitors, self.url)
            competitor_score = int(competitor_data.get("top_competitor_score", 85))
        except Exception as e:
            logger.warning(f"Competitor comparison failed: {e}")
            competitor_score = 85

        # 8. Scoring & Charts
        # Refined Link Score: Deduct 10 points per broken link, starting from 100
        total_internal = links_data["internal_links_count"]
        broken_internal = links_data["broken_internal_links"]
        link_score = 100 if total_internal == 0 else max(0, 100 - (broken_internal * 10))
        
        # Perf Score: Standard curve
        base_perf = max(0, 100 - (lcp_ms / 30.0))
        cls_penalty = 20 if cls > 0.25 else 10 if cls > 0.1 else 0
        perf_score = max(0, min(100, base_perf - cls_penalty))

        # Overall Score calculation
        overall_raw = (onpage_score + link_score + perf_score + 90) / 4
        overall_score = round(max(0, min(100, overall_raw)))

        grade_letter = (
            "A+" if overall_score >= 90 else
            "A"  if overall_score >= 80 else
            "B"  if overall_score >= 70 else
            "C"  if overall_score >= 60 else
            "D"
        )

        chart_data = {
            "bar": {
                "labels": ["SEO", "Links", "Perf", "AI"],
                "data": [onpage_score, link_score, perf_score, 90],
            },
            "radar": {
                "labels": ["SEO", "Links", "Perf", "AI"],
                "data": [onpage_score, link_score, perf_score, 90],
            },
            "doughnut": {
                "labels": ["Good", "Warning", "Broken"],
                "data": [
                    max(0, links_data["internal_links_count"] - links_data["broken_internal_links"]),
                    links_data["warning_links_count"],
                    links_data["broken_internal_links"],
                ],
            },
        }

        await send_update(100, "Audit complete.", finished=True)

        return {
            "overall_score": overall_score,
            "grade": grade_letter,
            "pages_graded": graded_pages,
            "breakdown": {
                "seo": onpage_score,
                "links": links_data,
                "performance": {"lcp_ms": lcp_ms, "cls": cls},
                "competitors": {"top_competitor_score": competitor_score},
            },
            "chart_data": chart_data,
            "audit_time": round(asyncio.get_event_loop().time() - start_time, 2),
        }
