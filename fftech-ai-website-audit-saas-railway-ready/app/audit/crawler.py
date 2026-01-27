import asyncio
from typing import Dict, Set
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from collections import deque


def _normalize_netloc(netloc: str) -> str:
    """Remove www. prefix and lower-case for domain comparison."""
    return netloc.lower().removeprefix("www.")


async def crawl_site(
    start_url: str,
    max_pages: int = 10,
    timeout: float = 10.0,
    max_concurrency: int = 8,
    user_agent: str = "FFTech-AuditBot/1.0 (+https://yourdomain.com)",
) -> Dict[str, str]:
    """
    Fast, polite, concurrent crawler that stays on the same domain.
    Returns {url: html_content} for successfully fetched pages.

    Features:
    - Concurrent fetching with controlled concurrency
    - Efficient queue (deque) + seen set
    - Respectful delays & user-agent
    - Proper URL normalization & same-site check
    - Handles redirects & errors gracefully
    """
    if max_pages < 1:
        return {}

    start_parsed = urlparse(start_url)
    if not start_parsed.scheme or not start_parsed.netloc:
        raise ValueError("Invalid start URL (must include scheme and netloc)")

    base_netloc_norm = _normalize_netloc(start_parsed.netloc)

    visited: Set[str] = set()
    queue: deque[str] = deque([start_url])
    results: Dict[str, str] = {}

    headers = {"User-Agent": user_agent}

    # Shared client for connection pooling
    limits = httpx.Limits(max_connections=max_concurrency, max_keepalive_connections=max_concurrency)
    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        headers=headers,
        verify=False,
        follow_redirects=True
    ) as client:

        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch_one(url: str) -> None:
            async with semaphore:
                if url in visited:
                    return

                visited.add(url)

                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        return

                    html = resp.text
                    results[url] = html

                    # Early exit if we already reached the limit
                    if len(results) >= max_pages:
                        return

                    # Parse for new links
                    soup = BeautifulSoup(html, "lxml")  # faster parser
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                            continue

                        next_url = urljoin(url, href)
                        next_parsed = urlparse(next_url)

                        # Must have scheme & netloc & same site
                        if (
                            next_parsed.scheme in ("http", "https")
                            and next_parsed.netloc
                            and _normalize_netloc(next_parsed.netloc) == base_netloc_norm
                            and next_url not in visited
                        ):
                            queue.append(next_url)

                except (httpx.RequestError, httpx.TimeoutException):
                    pass  # silent fail – continue crawling

        # Main crawl loop
        while queue and len(results) < max_pages:
            # Take up to concurrency limit tasks
            current_batch = []
            for _ in range(min(len(queue), max_concurrency)):
                if not queue:
                    break
                url = queue.popleft()
                if url not in visited:
                    current_batch.append(fetch_one(url))

            if not current_batch:
                break

            await asyncio.gather(*current_batch, return_exceptions=True)

            # Small politeness delay between batches
            await asyncio.sleep(0.1)

    return results
