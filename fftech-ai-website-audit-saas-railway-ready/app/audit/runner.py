# app/audit/runner.py
import asyncio
import logging
from typing import Optional, Callable, Dict, Any, List

from .crawler import crawl
from .seo import analyze_onpage
from .grader import grade_website
from .links import analyze_links_async
from .record import fetch_site_html
from .psi import fetch_lighthouse
from .competitor_report import compare_with_competitors

logger = logging.getLogger("audit_engine")


# ---- Direct HTML fetch fallback for protected sites (Cloudflare/WAF) ----
async def _direct_fetch_html(url: str) -> List[Dict[str, str]]:
    """
    A minimal, resilient fetch that mimics a browser to retrieve at least the
    root HTML so SEO/Links/Grading have something to process if crawler fails.
    """
    try:
        # Use httpx only when available in your environment
        import httpx
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        }
        timeout = httpx.Timeout(15.0, connect=10.0)
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=timeout,
            verify=True,
        ) as client:
            resp = await client.get(url)
            text = resp.text or ""
            if text.strip():
                return [{"url": str(resp.url), "html": text}]
    except Exception as e:
        logger.warning("Direct fetch fallback failed for %s: %s", url, e)
    return []


class WebsiteAuditRunner:
    """
    Integrated runner for FFTech AI Website Audit.
    Crawls, grades, analyzes SEO, links, performance, and competitors.
    """

    def __init__(self, url: str, max_pages: int = 20, psi_api_key: Optional[str] = None):
        self.url = url
        self.max_pages = max_pages
        self.psi_api_key = psi_api_key

    async def run_audit(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        start_time = asyncio.get_event_loop().time()

        async def send_update(pct: float, msg: str):
            if progress_callback:
                payload = {"crawl_progress": pct, "status": msg, "finished": False}
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(payload)
                else:
                    progress_callback(payload)

        # ------------------- 1️⃣ Crawl pages -------------------
        await send_update(5, "Crawling internal pages…")
        try:
            crawl_result = await crawl(self.url, max_pages=self.max_pages)
            pages: List[Dict[str, Any]] = crawl_result.get("report", []) or []
        except Exception as e:
            logger.exception("Crawler failed: %s", e)
            pages = []

        # ------------------- 2️⃣ Fetch raw HTML -------------------
        await send_update(15, "Fetching page HTML…")
        try:
            html_docs: List[Dict[str, Any]] = await asyncio.to_thread(fetch_site_html, self.url, self.max_pages)
        except Exception as e:
            logger.exception("fetch_site_html failed: %s", e)
            html_docs = []

        # If both are empty or don't contain HTML, try direct fetch fallback
        has_html_in_pages = any(bool(p.get("html")) for p in pages)
        if not html_docs and not has_html_in_pages:
            await send_update(22, "Direct fetching homepage HTML…")
            html_docs = await _direct_fetch_html(self.url)

        # Prepare documents for SEO/grading
        pages_for_seo: List[Dict[str, Any]] = pages
        has_any_html_in_pages = any(bool(p.get("html")) for p in pages)
        if not pages or not has_any_html_in_pages:
            if html_docs:
                pages_for_seo = [
                    {"url": d.get("url", self.url), "html": d.get("html", "")}
                    for d in html_docs[: self.max_pages]
                ]
                logger.info("Using html_docs for SEO/Grading (crawler pages lacked HTML).")
            else:
                # As a last resort, give at least one empty page to keep pipeline alive
                pages_for_seo = [{"url": self.url, "html": ""}]
                logger.warning("No HTML available; SEO analysis will be minimal.")

        # ------------------- 3️⃣ SEO Analysis -------------------
        await send_update(30, "Analyzing SEO heuristics…")
        try:
            seo_data = await analyze_onpage(pages_for_seo)
            onpage_score = round(seo_data.get("score", 0)) if isinstance(seo_data, dict) else 0
        except Exception as e:
            logger.exception("SEO analysis failed: %s", e)
            onpage_score = 0

        # ------------------- 4️⃣ Link Analysis -------------------
        await send_update(50, "Checking internal and external links…")
        try:
            links_data_raw = await analyze_links_async(html_docs or pages_for_seo, self.url, progress_callback=progress_callback)
        except Exception as e:
            logger.exception("Link analysis failed: %s", e)
            links_data_raw = {}

        links_data = {
            "internal_links_count": int(links_data_raw.get("internal_links_count", 0) or 0),
            "external_links_count": int(links_data_raw.get("external_links_count", 0) or 0),
            "broken_internal_links": int(links_data_raw.get("broken_internal_links", 0) or 0),
            "warning_links_count": int(links_data_raw.get("warning_links_count", 0) or 0),
        }

        # ------------------- 5️⃣ Performance Metrics -------------------
        await send_update(70, "Fetching PageSpeed metrics…")
        psi_data: Dict[str, Any] = {"lcp_ms": 0, "cls": 0}
        if self.psi_api_key:
            try:
                psi_data = await asyncio.to_thread(fetch_lighthouse, self.url, api_key=self.psi_api_key)
            except Exception as e:
                logger.warning("PSI fetch failed: %s", e)

        lcp_ms = float(psi_data.get("lcp_ms", 0) or 0.0)
        cls = float(psi_data.get("cls", 0) or 0.0)

        # ------------------- 6️⃣ Page Grading -------------------
        await send_update(80, "Grading pages…")
        graded_pages = []
        for page in (pages_for_seo or []):
            html_content = page.get("html", "") or ""
            page_url = page.get("url", "") or ""
            try:
                grade = grade_website(html_content, page_url)
            except Exception as e:
                logger.warning("grade_website failed for %s: %s", page_url, e)
                grade = "D"
            graded_pages.append({"url": page_url, "grade": grade})

        # ------------------- 7️⃣ Competitor Comparison -------------------
        await send_update(90, "Analyzing competitors…")
        try:
            competitor_data = await asyncio.to_thread(compare_with_competitors, self.url)
        except Exception as e:
            logger.warning("Competitor analysis failed: %s", e)
            competitor_data = {}
        competitor_score = int(competitor_data.get("top_competitor_score", 0) or 0)

        # ------------------- 8️⃣ Aggregate final report -------------------
        link_score = max(0, min(links_data.get("internal_links_count", 0), 100))
        perf_score = max(0, min(100 - (lcp_ms / 50.0), 100))  # 0ms => 100

        # Keep AI confidence at 90 (as per your chart)
        overall_score = round((onpage_score + link_score + perf_score + 90) / 4)
        overall_score = max(0, min(overall_score, 100))

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
                    links_data.get("internal_links_count", 0),
                    links_data.get("warning_links_count", 0),
                    links_data.get("broken_internal_links", 0),
                ],
            },
        }

        await send_update(100, "Audit complete.")

        grade_letter = (
            "A+" if overall_score >= 90 else
            "A"  if overall_score >= 80 else
            "B"  if overall_score >= 70 else
            "C"  if overall_score >= 60 else
            "D"
        )

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
