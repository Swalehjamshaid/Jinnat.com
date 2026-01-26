# app/audit/crawler.py
import asyncio, logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("audit_engine")

async def fetch_page(client, url):
    try:
        resp = await client.get(url, timeout=15)
        html = resp.text
        return html, resp.status_code
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return "", None

async def async_crawl(start_url: str, max_pages: int = 15, websocket=None):
    """
    Async crawler for fast internal/external link extraction
    Returns: dict with unique_internal, unique_external, broken_internal, broken_external
    """
    parsed_root = urlparse(start_url)
    domain = parsed_root.netloc

    visited = set()
    internal_links = set()
    external_links = set()
    broken_internal = set()
    broken_external = set()
    queue = [start_url]

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            html, status = await fetch_page(client, url)
            if status is None or status >= 400:
                if domain in url:
                    broken_internal.add(url)
                else:
                    broken_external.add(url)
                continue

            soup = BeautifulSoup(html, "lxml")
            links = [a.get("href") for a in soup.find_all("a", href=True)]
            for link in links:
                absolute = urljoin(url, link)
                link_domain = urlparse(absolute).netloc
                if link_domain == domain:
                    if absolute not in visited:
                        queue.append(absolute)
                        internal_links.add(absolute)
                else:
                    external_links.add(absolute)

            if websocket:
                await websocket.send_json({"status": "crawling", "message": f"Crawled {len(visited)} pages..."})

    return {
        "unique_internal": len(internal_links),
        "unique_external": len(external_links),
        "broken_internal": len(broken_internal),
        "broken_external": len(broken_external),
        "crawled_count": len(visited)
    }
