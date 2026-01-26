# app/audit/crawler.py
import asyncio
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("audit_engine")

MAX_CONCURRENT_REQUESTS = 10  # limit concurrent fetches for speed & stability
MAX_PAGES = 50  # increase pages to crawl for deeper audits
REQUEST_TIMEOUT = 10  # seconds

# ------------------------------
# Fetch a single page
# ------------------------------
async def fetch_page(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT)
        html = resp.text
        return html, resp.status_code
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return "", None

# ------------------------------
# Analyze SEO elements
# ------------------------------
def analyze_seo(html: str):
    """
    Extract key SEO metrics for a page.
    """
    soup = BeautifulSoup(html, "lxml")
    images = soup.find_all("img")
    images_missing_alt = sum(1 for img in images if not img.get("alt"))
    title = soup.find("title")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    return {
        "images_missing_alt": images_missing_alt,
        "title_missing": 0 if title and title.text.strip() else 1,
        "meta_description_missing": 0 if meta_desc and meta_desc.get("content") else 1
    }

# ------------------------------
# Crawl and collect links
# ------------------------------
async def async_crawl(start_url: str, max_pages: int = MAX_PAGES, websocket=None):
    parsed_root = urlparse(start_url)
    domain = parsed_root.netloc

    visited = set()
    internal_links = set()
    external_links = set()
    broken_internal = set()
    broken_external = set()
    results = []

    queue = [start_url]
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:

        async def crawl_page(url: str):
            async with semaphore:
                if url in visited:
                    return
                visited.add(url)

                html, status = await fetch_page(client, url)

                seo_data = {"images_missing_alt": 0, "title_missing": 0, "meta_description_missing": 0}

                if status is None or status >= 400:
                    if domain in url:
                        broken_internal.add(url)
                    else:
                        broken_external.add(url)
                else:
                    seo_data = analyze_seo(html)
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

                results.append({
                    "url": url,
                    "status": status or "failed",
                    "seo": seo_data
                })

                # Update progress via websocket if available
                if websocket:
                    await websocket.send_json({
                        "crawl_progress": round(len(visited) / max_pages * 100, 2),
                        "status": f"Crawled {len(visited)} pages...",
                        "finished": False
                    })

        # Crawl pages concurrently
        while queue and len(visited) < max_pages:
            tasks = [asyncio.create_task(crawl_page(queue.pop(0))) for _ in range(min(len(queue), MAX_CONCURRENT_REQUESTS))]
            await asyncio.gather(*tasks)

    # Aggregate SEO metrics
    total_images_missing_alt = sum(r["seo"]["images_missing_alt"] for r in results)
    total_title_missing = sum(r["seo"]["title_missing"] for r in results)
    total_meta_missing = sum(r["seo"]["meta_description_missing"] for r in results)

    return {
        "unique_internal": len(internal_links),
        "unique_external": len(external_links),
        "broken_internal": len(broken_internal),
        "broken_external": len(broken_external),
        "crawled_count": len(visited),
        "total_images_missing_alt": total_images_missing_alt,
        "total_titles_missing": total_title_missing,
        "total_meta_description_missing": total_meta_missing,
        "pages": results
    }
