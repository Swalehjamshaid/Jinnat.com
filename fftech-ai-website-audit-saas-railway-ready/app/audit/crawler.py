import asyncio
import httpx
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

# -------------------------
# Configuration
# -------------------------
MAX_PAGES = 20
CONCURRENCY = 10
TIMEOUT = 5.0

# -------------------------
# Fetch Page
# -------------------------
async def fast_fetch(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url, timeout=TIMEOUT, verify=False)
        return resp.text, resp.status_code
    except Exception:
        return "", 0

# -------------------------
# Crawl Website
# -------------------------
async def crawl(start_url: str, max_pages: int = MAX_PAGES):
    """
    Crawl website and return a list of page dictionaries:
    {"url": ..., "title": ..., "html": ...}
    """
    domain = urlparse(start_url).netloc
    visited = {start_url}
    to_crawl = [start_url]
    results = []

    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=5)

    async with httpx.AsyncClient(limits=limits, follow_redirects=True, verify=False) as client:
        while to_crawl and len(results) < max_pages:
            batch = to_crawl[:CONCURRENCY]
            to_crawl = to_crawl[CONCURRENCY:]

            tasks = [fast_fetch(client, url) for url in batch]
            responses = await asyncio.gather(*tasks)

            new_links = []

            for i, (html, status) in enumerate(responses):
                url = batch[i]
                if status == 200:
                    soup = BeautifulSoup(html, "lxml")

                    results.append({
                        "url": url,
                        "title": soup.title.string if soup.title else "N/A",
                        "html": html
                    })

                    # Add internal links for further crawling
                    if len(results) + len(to_crawl) < max_pages:
                        for a in soup.find_all("a", href=True):
                            link = urljoin(url, a["href"])
                            if urlparse(link).netloc == domain and link not in visited:
                                visited.add(link)
                                new_links.append(link)

            to_crawl.extend(new_links)

    return {"report": results}
