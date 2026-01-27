# app/audit/crawler.py
import asyncio
from typing import Dict, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

def _same_site(a: str, b: str) -> bool:
    return a.lower().lstrip("www.") == b.lower().lstrip("www.")


async def crawl_site(
    start_url: str,
    max_pages: int = 10,
    timeout: float = 10.0,
) -> Dict[str, str]:
    """
    Minimal async crawler: fetch up to `max_pages` pages on the same site.
    Returns dict {url: html}.
    """
    parsed_start = urlparse(start_url)
    base_netloc = parsed_start.netloc
    to_visit: Set[str] = {start_url}
    seen: Set[str] = set()
    pages: Dict[str, str] = {}

    async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
        while to_visit and len(pages) < max_pages:
            url = to_visit.pop()
            if url in seen:
                continue
            seen.add(url)

            try:
                resp = await client.get(url, follow_redirects=True)
                html = resp.text
                pages[url] = html
            except Exception:
                continue

            # Extract internal links from this page
            soup = BeautifulSoup(html or "", "html.parser")
            for a in soup.find_all("a"):
                href = (a.get("href") or "").strip()
                if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                abs_url = urljoin(url, href)
                parsed = urlparse(abs_url)
                if parsed.scheme and parsed.netloc and _same_site(parsed.netloc, base_netloc):
                    if abs_url not in seen and len(pages) + len(to_visit) < max_pages:
                        to_visit.add(abs_url)

            # be polite
            await asyncio.sleep(0.05)

    return pages
