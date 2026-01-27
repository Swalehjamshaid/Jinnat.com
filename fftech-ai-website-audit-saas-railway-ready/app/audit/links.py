from typing import Dict, Any, Set
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import asyncio
import httpx
import logging

logger = logging.getLogger("audit_engine")
MAX_CONCURRENT_LINKS = 10
LINK_TIMEOUT = 5

async def check_link(client: httpx.AsyncClient, url: str) -> bool:
    """Returns True if link is broken."""
    try:
        resp = await client.head(url, timeout=LINK_TIMEOUT, follow_redirects=True)
        return resp.status_code >= 400
    except Exception:
        return True

async def analyze_links_async(html_docs: Dict[str, str], base_url: str, progress_callback=None) -> Dict[str, Any]:
    internal_links: Set[str] = set()
    external_links: Set[str] = set()
    broken_internal: Set[str] = set()
    broken_external: Set[str] = set()
    tasks = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LINKS)
    urls_to_check = []

    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    for html in html_docs.values():
        soup = BeautifulSoup(html, 'lxml')
        for a in soup.find_all('a', href=True):
            href = a['href']
            parsed = urlparse(urljoin(base_url, href))
            normalized = parsed._replace(fragment="").geturl()
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc == base_domain:
                internal_links.add(normalized)
                urls_to_check.append((normalized, True))
            else:
                external_links.add(normalized)
                urls_to_check.append((normalized, False))

    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        async def worker(url_tuple):
            url, is_internal = url_tuple
            async with semaphore:
                if await check_link(client, url):
                    if is_internal:
                        broken_internal.add(url)
                    else:
                        broken_external.add(url)

        for url_tuple in urls_to_check:
            tasks.append(worker(url_tuple))

        total_tasks = len(tasks)
        for i, t in enumerate(asyncio.as_completed(tasks), start=1):
            await t
            if progress_callback:
                await progress_callback({
                    "crawl_progress": round(i / total_tasks * 100, 2),
                    "status": f"Checked {i}/{total_tasks} links…",
                    "finished": False
                })

    if progress_callback:
        await progress_callback({
            "crawl_progress": 100,
            "status": f"Link analysis complete ({len(internal_links)} internal, {len(external_links)} external)",
            "finished": True
        })

    return {
        "internal_links_count": len(internal_links),
        "external_links_count": len(external_links),
        "broken_internal_links": len(broken_internal),
        "broken_external_links": len(broken_external),
        "broken_internal_urls": list(broken_internal),
        "broken_external_urls": list(broken_external),
    }
