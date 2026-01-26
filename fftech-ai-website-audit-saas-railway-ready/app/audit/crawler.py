
# app/audit/crawler.py
import asyncio
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("audit_engine")

MAX_CONCURRENT_REQUESTS = 10
MAX_PAGES = 50
REQUEST_TIMEOUT = 10

async def fetch_page(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT)
        return resp.text, resp.status_code
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return "", None

def analyze_seo(html: str):
    soup = BeautifulSoup(html, "lxml")
    images = soup.find_all("img")
    images_missing_alt = sum(1 for img in images if not img.get("alt"))

    title = soup.find("title")
    meta_desc = soup.find("meta", attrs={"name": "description"})

    return {
        "images_missing_alt": images_missing_alt,
        "title_missing": 0 if title and title.text.strip() else 1,
        "meta_description_missing": 0 if meta_desc and meta_desc.get("content") else 1,
    }

async def async_crawl(start_url: str, max_pages: int = MAX_PAGES, websocket=None):

    parsed = urlparse(start_url)
    domain = parsed.netloc

    visited = set()
    internal_links = set()
    external_links = set()
    broken_internal = set()
    broken_external = set()
    results = []

    queue = asyncio.Queue()
    await queue.put(start_url)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:

        async def worker():
            while len(visited) < max_pages:
                try:
                    url = await asyncio.wait_for(queue.get(), timeout=2)
                except asyncio.TimeoutError:
                    return

                async with semaphore:
                    if url in visited:
                        queue.task_done()
                        continue

                    visited.add(url)
                    html, status = await fetch_page(client, url)

                    seo_data = {"images_missing_alt": 0, "title_missing": 0, "meta_description_missing": 0}

                    if not status or status >= 400:
                        if domain in url:
                            broken_internal.add(url)
                        else:
                            broken_external.add(url)
                    else:
                        seo_data = analyze_seo(html)

                        soup = BeautifulSoup(html, "lxml")
                        for tag in soup.find_all("a", href=True):
                            link = urljoin(url, tag.get("href"))
                            link_domain = urlparse(link).netloc

                            if link_domain == domain:
                                if link not in visited:
                                    internal_links.add(link)
                                    await queue.put(link)
                            else:
                                external_links.add(link)

                    results.append({
                        "url": url,
                        "status": status or "failed",
                        "seo": seo_data,
                    })

                    if websocket:
                        await websocket.send_json({
                            "crawl_progress": round(len(visited) / max_pages * 100, 2),
                            "status": f"Crawled {len(visited)} pages...",
                            "finished": False
                        })

                    queue.task_done()

        # Launch workers
        workers = [asyncio.create_task(worker()) for _ in range(MAX_CONCURRENT_REQUESTS)]
        await queue.join()

        for w in workers:
            w.cancel()

    return {
        "unique_internal": len(internal_links),
        "unique_external": len(external_links),
        "broken_internal": len(broken_internal),
        "broken_external": len(broken_external),
        "crawled_count": len(visited),
        "total_images_missing_alt": sum(r["seo"]["images_missing_alt"] for r in results),
        "total_titles_missing": sum(r["seo"]["title_missing"] for r in results),
        "total_meta_description_missing": sum(r["seo"]["meta_description_missing"] for r in results),
        "pages": results
    }
``
