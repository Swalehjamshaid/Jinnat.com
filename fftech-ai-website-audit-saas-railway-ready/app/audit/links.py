import asyncio
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import httpx
import logging

logger = logging.getLogger("audit_engine")

# -----------------------------
# Helper function to fetch links from a single HTML page
# -----------------------------
async def extract_links_from_html(html: str, base_url: str) -> Dict[str, int]:
    internal_links = set()
    external_links = set()
    broken_internal_links = set()
    warning_links = set()

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("a", href=True):
        href = tag.get("href").strip()
        if href.startswith("#") or href.lower().startswith("mailto:"):
            continue
        parsed_href = urlparse(href)
        if parsed_href.netloc and parsed_href.netloc != urlparse(base_url).netloc:
            external_links.add(href)
        else:
            internal_links.add(href)

    # Optionally, simulate broken/warning detection
    # For simplicity, we'll just mark 0 broken links here
    return {
        "internal_links_count": len(internal_links),
        "external_links_count": len(external_links),
        "broken_internal_links": len(broken_internal_links),
        "warning_links_count": len(warning_links)
    }

# -----------------------------
# Main async function
# -----------------------------
async def analyze_links_async(html_docs: Dict[str, str], base_url: str, progress_callback: Optional[Any] = None) -> Dict[str, Any]:
    if asyncio.iscoroutine(html_docs):
        html_docs = await html_docs  # ensure we await any coroutine

    results = {}
    total = len(html_docs)
    count = 0

    for page_url, html in html_docs.items():
        page_result = await extract_links_from_html(html, base_url)
        results[page_url] = page_result
        count += 1
        if progress_callback:
            pct = 50 + int(40 * count / total)  # progress from 50% -> 90%
            update = {"status": f"Analyzing links {count}/{total}", "crawl_progress": pct, "finished": False}
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(update)
            else:
                progress_callback(update)

    # Aggregate final results
    aggregate = {
        "internal_links_count": sum(r.get("internal_links_count", 0) for r in results.values()),
        "external_links_count": sum(r.get("external_links_count", 0) for r in results.values()),
        "broken_internal_links": sum(r.get("broken_internal_links", 0) for r in results.values()),
        "warning_links_count": sum(r.get("warning_links_count", 0) for r in results.values())
    }

    return aggregate
