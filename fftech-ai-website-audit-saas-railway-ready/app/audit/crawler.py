# fftech-ai-website-audit-saas-railway-ready/app/audit/crawler.py

import asyncio
import logging
from urllib.parse import urlparse, urljoin
from typing import Dict, Set, List, Callable, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("audit_engine")

MAX_PAGES = 50
MAX_CONCURRENCY = 10
TIMEOUT = 12


async def fetch(client: httpx.AsyncClient, url: str) -> tuple[str, int]:
    """Fetch page with retry logic."""
    try:
        resp = await client.get(url, timeout=TIMEOUT)
        return resp.text, resp.status_code
    except Exception as e:
        logger.warning(f"Failed fetching {url}: {e}")
        return "", 0


def analyze(html: str) -> Dict[str, int]:
    """Basic SEO metrics."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.find("title")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    return {
        "images_missing_alt": sum(1 for img in soup.find_all("img") if not img.get("alt")),
        "title_missing": 0 if title and title.text.strip() else 1,
        "meta_description_missing": 0 if meta_desc and meta_desc.get("content") else 1,
    }


async def async_crawl(
    start_url: str,
    max_pages: int = MAX_PAGES,
    progress_callback: Optional[Callable] = None
) -> Dict:

    parsed = urlparse(start_url)
    domain = parsed.netloc

    visited: Set[str] = set()
    internal_links: Set[str] = set()
    external_links: Set[str] = set()
    broken_internal: Set[str] = set()
    broken_external: Set[str] = set()
    results: List[Dict] = []

    queue = asyncio.Queue()
    await queue.put(start_url)
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async with httpx.AsyncClient(follow_redirects=True) as client:

        async def worker():
            while not queue.empty() and len(visited) < max_pages:
                url = await queue.get()
                if url in visited:
                    continue
                visited.add(url)

                async with semaphore:
                    html, status = await fetch(client, url)

                seo_data = analyze(html) if status and status < 400 else {
                    "images_missing_alt": 0,
                    "title_missing": 0,
                    "meta_description_missing": 0,
                }

                if not status or status >= 400:
                    if domain in urlparse(url).netloc:
                        broken_internal.add(url)
                    else:
                        broken_external.add(url)
                else:
                    soup = BeautifulSoup(html, "lxml")
                    for tag in soup.find_all("a", href=True):
                        link = urljoin(url, tag["href"])
                        parsed_link = urlparse(link)
                        normalized = parsed_link._replace(fragment="").geturl()

                        if parsed_link.scheme not in ("http", "https"):
                            continue

                        if parsed_link.netloc == domain:
                            internal_links.add(normalized)
                            if normalized not in visited:
                                await queue.put(normalized)
                        else:
                            external_links.add(normalized)

                results.append({"url": url, "status": status, "seo": seo_data})

                if progress_callback:
                    await progress_callback({
                        "crawl_progress": round(len(visited) / max_pages * 100, 2),
                        "status": f"Crawled {len(visited)} pages…",
                        "finished": False
                    })

        workers = [asyncio.create_task(worker()) for _ in range(MAX_CONCURRENCY)]
        await asyncio.gather(*workers)

    return {
        "report": results,
        "unique_internal": len(internal_links),
        "unique_external": len(external_links),
        "broken_internal": list(broken_internal),
        "broken_external": list(broken_external),
    }
