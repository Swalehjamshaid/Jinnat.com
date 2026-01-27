import asyncio
import random
from typing import Dict, Set, Optional
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque
import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass


@dataclass(frozen=True)
class CrawlConfig:
    max_pages: int = 10
    timeout: float = 10.0
    max_concurrency: int = 8
    politeness_delay_min: float = 0.08
    politeness_delay_max: float = 0.25
    user_agent: str = "FFTech-AuditBot/1.0 (+https://yourdomain.com)"
    max_depth: Optional[int] = None


def _normalize_netloc(netloc: str) -> str:
    return netloc.lower().removeprefix("www.").rstrip(".")


def _normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    return parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=_normalize_netloc(parsed.netloc)
    ).geturl()


async def crawl_site(
    start_url: str,
    max_pages: int = 10,
    timeout: float = 10.0,
    max_concurrency: int = 8,
    user_agent: str = "FFTech-AuditBot/1.0 (+https://yourdomain.com)",
) -> Dict[str, str]:

    if max_pages < 1:
        return {}

    parsed_start = urlparse(start_url)
    if not parsed_start.scheme or not parsed_start.netloc:
        raise ValueError("Invalid start URL")

    base_domain = _normalize_netloc(parsed_start.netloc)

    visited: Set[str] = set()
    queue: deque[str] = deque([_normalize_url(start_url)])
    results: Dict[str, str] = {}

    limits = httpx.Limits(
        max_connections=max_concurrency,
        max_keepalive_connections=max_concurrency,
        keepalive_expiry=30.0
    )

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        headers=headers,
        limits=limits,
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        http2=True,
        verify=True
    ) as client:

        semaphore = asyncio.Semaphore(max_concurrency)

        async def fetch(url: str) -> None:
            async with semaphore:
                if url in visited or len(results) >= max_pages:
                    return

                visited.add(url)

                try:
                    response = await client.get(url)
                except httpx.HTTPError:
                    return

                if response.status_code != 200:
                    return

                if "text/html" not in response.headers.get("content-type", "").lower():
                    return

                html = response.text
                results[url] = html

                if len(results) >= max_pages:
                    return

                soup = BeautifulSoup(html, "lxml")

                for tag in soup.select("a[href]"):
                    href = tag.get("href", "").strip()
                    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                        continue

                    next_url = _normalize_url(urljoin(url, href))
                    parsed = urlparse(next_url)

                    if (
                        parsed.scheme in ("http", "https")
                        and _normalize_netloc(parsed.netloc) == base_domain
                        and next_url not in visited
                    ):
                        queue.append(next_url)

        while queue and len(results) < max_pages:
            tasks = []

            for _ in range(min(len(queue), max_concurrency)):
                tasks.append(fetch(queue.popleft()))

            await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(random.uniform(0.08, 0.25))

    return results
