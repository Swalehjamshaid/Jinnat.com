import asyncio
from typing import Dict, List, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag
import httpx


async def analyze_links_async(
    html_dict: Dict[str, str],
    base_url: str,
    callback: Any = None
) -> Dict[str, Any]:
    """
    High-performance, concurrent link analyzer.

    Features:
    - Fast concurrent HEAD checks with semaphore
    - Proper absolute URL resolution
    - Internal/external classification (normalized domain)
    - Broken link detection (status >= 400 or exception)
    - Preserves exact same input/output structure
    - Added progress feedback & early exit
    - Handles malformed/relative/absolute URLs safely
    """
    html = html_dict.get(base_url, "")
    if not html:
        if callback:
            await callback({"status": "No HTML content received", "crawl_progress": 70})
        return {
            "internal_links_count": 0,
            "external_links_count": 0,
            "broken_internal_links": 0,
            "broken_links_list": []
        }

    soup = BeautifulSoup(html, "lxml")  # faster parser (install lxml if possible)

    # Extract all <a href> tags
    link_tags: List[Tag] = soup.find_all("a", href=True)
    total_links = len(link_tags)

    if callback:
        await callback({
            "status": f"Found {total_links} potential links – analyzing...",
            "crawl_progress": 65
        })

    # Normalize base domain for comparison
    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc.lower().removeprefix("www.")

    internal: set[str] = set()
    external: set[str] = set()
    to_check: List[str] = []

    # ──── Phase 1: Classify links ────────────────────────────────────────
    for tag in link_tags:
        href = tag["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        # Resolve to absolute URL
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Skip invalid or non-http(s) schemes
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue

        # Normalize domain for comparison
        link_domain = parsed.netloc.lower().removeprefix("www.")

        if link_domain == base_domain:
            internal.add(full_url)
        else:
            external.add(full_url)

        # Queue for broken check (only internal for performance)
        if link_domain == base_domain:
            to_check.append(full_url)

    # ──── Phase 2: Concurrent broken link checking ───────────────────────
    broken: List[str] = []
    semaphore = asyncio.Semaphore(20)  # safe concurrency limit

    async def check_one(url: str) -> None:
        async with semaphore:
            try:
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                    r = await client.head(url, timeout=4.0)
                    if r.status_code >= 400:
                        broken.append(url)
            except (httpx.RequestError, httpx.TimeoutException):
                broken.append(url)  # treat errors/timeouts as broken

    if to_check:
        if callback:
            await callback({
                "status": f"Validating {min(len(to_check), 50)} internal links...",
                "crawl_progress": 75
            })

        # Limit checks to avoid abuse / slow sites
        check_tasks = [check_one(url) for url in to_check[:50]]
        await asyncio.gather(*check_tasks, return_exceptions=True)

    # ──── Final result (same structure as before) ────────────────────────
    result = {
        "internal_links_count": len(internal),
        "external_links_count": len(external),
        "broken_internal_links": len(broken),
        "broken_links_list": broken[:10]  # limit list size for response
    }

    if callback:
        await callback({
            "status": f"Links analyzed: {len(internal)} internal, {len(external)} external, {len(broken)} broken",
            "crawl_progress": 95
        })

    return result
