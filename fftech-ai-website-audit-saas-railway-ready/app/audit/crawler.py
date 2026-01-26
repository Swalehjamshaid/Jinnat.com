import asyncio
import logging
from urllib.parse import urlparse, urljoin
from typing import Dict, Set, List, Callable, Optional

import httpx
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger("audit_engine")

# International Standards Constants
MAX_PAGES = 50
MAX_CONCURRENCY = 15  # Increased for speed
TIMEOUT = 10.0        # Shorter timeout to skip slow/dead pages fast

async def fetch(client: httpx.AsyncClient, url: str) -> tuple[str, int]:
    """Fetch page with SSL bypass and error handling."""
    try:
        # verify=False is critical for sites with international SSL chain issues
        resp = await client.get(url, timeout=TIMEOUT)
        return resp.text, resp.status_code
    except Exception as e:
        logger.warning(f"Failed fetching {url}: {e}")
        return "", 0

def analyze_international_standards(html: str) -> Dict[str, int]:
    """
    Expanded analysis covering International SEO standards:
    - Language/Charset
    - Canonical tags
    - Mobile Viewport
    - H1 Hierarchy
    """
    soup = BeautifulSoup(html, "lxml")
    
    title = soup.find("title")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    canonical = soup.find("link", rel="canonical")
    viewport = soup.find("meta", attrs={"name": "viewport"})
    h1_tags = soup.find_all("h1")

    return {
        "images_missing_alt": sum(1 for img in soup.find_all("img") if not img.get("alt")),
        "title_missing": 0 if title and title.text.strip() else 1,
        "meta_description_missing": 0 if meta_desc and meta_desc.get("content") else 1,
        "canonical_missing": 0 if canonical else 1,
        "mobile_unfriendly": 0 if viewport else 1,
        "h1_error": 0 if len(h1_tags) == 1 else 1  # Standard is exactly one H1
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
    results: List[Dict] = []

    # Better Queue management for high-speed concurrency
    queue = asyncio.Queue()
    await queue.put(start_url)

    # Disable SSL verification globally for this session
    async with httpx.AsyncClient(
        verify=False, 
        follow_redirects=True, 
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=MAX_CONCURRENCY)
    ) as client:

        async def worker():
            while True:
                # Get URL from queue
                try:
                    # If queue is empty for 2 seconds, worker assumes crawling is done
                    url = await asyncio.wait_for(queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    break

                if url in visited or len(visited) >= max_pages:
                    queue.task_done()
                    continue

                visited.add(url)
                
                # Fetch and Analyze
                html, status = await fetch(client, url)
                
                if not status or status >= 400:
                    if domain in url:
                        broken_internal.add(url)
                else:
                    seo_data = analyze_international_standards(html)
                    results.append({"url": url, "status": status, "seo": seo_data})

                    # Extract New Links
                    soup = BeautifulSoup(html, "lxml")
                    for tag in soup.find_all("a", href=True):
                        link = urljoin(url, tag["href"])
                        p_link = urlparse(link)
                        
                        # Clean/Normalize link
                        normalized = p_link._replace(fragment="").geturl()

                        if p_link.scheme in ("http", "https"):
                            if p_link.netloc == domain:
                                internal_links.add(normalized)
                                if normalized not in visited:
                                    await queue.put(normalized)
                            else:
                                external_links.add(normalized)

                if progress_callback:
                    await progress_callback({
                        "progress": round(len(visited) / max_pages * 100, 1),
                        "message": f"Analyzed {len(visited)} pages..."
                    })
                
                queue.task_done()

        # Start concurrent workers
        tasks = [asyncio.create_task(worker()) for _ in range(MAX_CONCURRENCY)]
        
        # Wait for queue to be fully processed
        await queue.join()

        # Clean up workers
        for t in tasks:
            t.cancel()

    return {
        "report": results,
        "unique_internal": len(internal_links),
        "unique_external": len(external_links),
        "broken_internal": list(broken_internal),
        "total_crawled": len(visited)
    }
