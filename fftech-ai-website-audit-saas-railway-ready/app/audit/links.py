import asyncio
import logging
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

# Limit concurrency to 10 to prevent the server from hanging
sem = asyncio.Semaphore(10)

async def check_single_link(client: httpx.AsyncClient, link: str) -> bool:
    """Returns True if the link is broken (4xx/5xx) or times out."""
    async with sem:
        try:
            # Strict 3-second timeout per link validation
            resp = await client.head(link, follow_redirects=True, timeout=3.0)
            return resp.status_code >= 400
        except Exception:
            return True # Connection errors/timeouts counted as broken

async def extract_links_from_html(html: str, base_url: str) -> Dict[str, int]:
    if not html.strip():
        return {"internal_links_count": 0, "broken_internal_links": 0, "warning_links_count": 0}

    soup = BeautifulSoup(html, "html.parser")
    internal, external, warnings = set(), set(), set()
    base_domain = urlparse(base_url).netloc.lower()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "tel:", "mailto:")):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if not parsed.scheme or not parsed.netloc:
            warnings.add(full_url)
            continue
        if parsed.netloc.lower() == base_domain:
            internal.add(full_url)
        else:
            external.add(full_url)

    # Performance: Check a sample (first 15) to maintain high speed
    to_check = list(internal)[:15]
    broken_count = 0
    if to_check:
        async with httpx.AsyncClient(verify=False) as client:
            tasks = [check_single_link(client, link) for link in to_check]
            results = await asyncio.gather(*tasks)
            broken_count = sum(1 for is_broken in results if is_broken)

    return {
        "internal_links_count": len(internal),
        "external_links_count": len(external),
        "broken_internal_links": broken_count,
        "warning_links_count": len(warnings)
    }

async def analyze_links_async(html_input: Dict[str, str], base_url: str, progress_callback: Optional[Any] = None) -> Dict[str, Any]:
    page_url = next(iter(html_input))
    html = html_input[page_url]
    if progress_callback:
        await progress_callback({"status": "🔗 Validating link integrity...", "crawl_progress": 75})
    return await extract_links_from_html(html, base_url)
