import asyncio
import logging
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("audit_engine")


async def extract_links_from_html(html: str, base_url: str) -> Dict[str, int]:
    """Extract and classify links from a single page's HTML."""
    if not html.strip():
        return {
            "internal_links_count": 0,
            "external_links_count": 0,
            "broken_internal_links": 0,
            "warning_links_count": 0
        }

    soup = BeautifulSoup(html, "html.parser")
    internal = set()
    external = set()
    broken_internal = set()
    warnings = set()

    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc.lower()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "tel:", "mailto:")):
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if not parsed.scheme or not parsed.netloc:
            warnings.add(full_url)  # malformed
            continue

        domain = parsed.netloc.lower()

        if domain == base_domain or domain.endswith("." + base_domain):
            internal.add(full_url)
        else:
            external.add(full_url)

    # Optional: Check broken internal links (slow – enable only if needed)
    # async with httpx.AsyncClient(timeout=5.0) as client:
    #     for link in internal:
    #         try:
    #             resp = await client.head(link, follow_redirects=True)
    #             if resp.status_code >= 400:
    #                 broken_internal.add(link)
    #         except Exception:
    #             broken_internal.add(link)

    return {
        "internal_links_count": len(internal),
        "external_links_count": len(external),
        "broken_internal_links": len(broken_internal),
        "warning_links_count": len(warnings)
    }


async def analyze_links_async(
    html_input: Union[List[Dict[str, str]], Dict[str, str]],
    base_url: str,
    progress_callback: Optional[Any] = None
) -> Dict[str, Any]:
    """Analyze links across multiple pages or single page."""
    # Normalize input to dict of url -> html
    html_docs: Dict[str, str] = {}

    if isinstance(html_input, list):
        for item in html_input:
            url = item.get("url", "unknown")
            html = item.get("html", "")
            if html.strip():
                html_docs[url] = html
    elif isinstance(html_input, dict):
        html_docs = {url: html for url, html in html_input.items() if html.strip()}
    else:
        logger.warning("Invalid html_input type for link analysis")
        html_docs = {}

    if not html_docs:
        logger.warning("No valid HTML provided for link analysis")
        return {
            "internal_links_count": 0,
            "external_links_count": 0,
            "broken_internal_links": 0,
            "warning_links_count": 0
        }

    results = {}
    total = len(html_docs)
    count = 0

    for page_url, html in html_docs.items():
        try:
            page_result = await extract_links_from_html(html, base_url)
            results[page_url] = page_result
        except Exception as e:
            logger.error(f"Link extraction failed for {page_url}: {e}")
            results[page_url] = {
                "internal_links_count": 0,
                "external_links_count": 0,
                "broken_internal_links": 0,
                "warning_links_count": 0
            }

        count += 1
        if progress_callback:
            pct = 50 + int(40 * count / total) if total > 0 else 90
            update = {"status": f"Analyzing links {count}/{total} pages", "crawl_progress": pct, "finished": False}
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(update)
                else:
                    progress_callback(update)
            except Exception:
                pass  # Don't crash if callback fails

    # Aggregate
    aggregate = {
        "internal_links_count": sum(r.get("internal_links_count", 0) for r in results.values()),
        "external_links_count": sum(r.get("external_links_count", 0) for r in results.values()),
        "broken_internal_links": sum(r.get("broken_internal_links", 0) for r in results.values()),
        "warning_links_count": sum(r.get("warning_links_count", 0) for r in results.values())
    }

    logger.info(f"Link analysis complete: {aggregate}")
    return aggregate
