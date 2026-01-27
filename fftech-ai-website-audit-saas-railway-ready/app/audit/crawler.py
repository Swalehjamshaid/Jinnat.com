# app/audit/crawler.py
import asyncio
import httpx
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

MAX_PAGES = 50
CONCURRENCY = 10
TIMEOUT = 5.0

async def fast_fetch(client: httpx.AsyncClient, url: str):
    """Fetch a URL asynchronously and return HTML and status."""
    try:
        resp = await client.get(url, timeout=TIMEOUT, follow_redirects=True, verify=False)
        return resp.text, resp.status_code
    except Exception:
        return "", 0

async def crawl(start_url: str, max_pages: int = MAX_PAGES):
    """Crawl website starting from start_url up to max_pages."""
    domain = urlparse(start_url).netloc
    visited = {start_url}
    to_crawl = [start_url]
    results = []

    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=5)

    async with httpx.AsyncClient(limits=limits) as client:
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
                    internal_links = external_links = broken_links = 0

                    for a in soup.find_all("a", href=True):
                        link = urljoin(url, a["href"])
                        if urlparse(link).netloc == domain:
                            internal_links += 1
                            if not link.startswith("http"):
                                broken_links += 1
                        else:
                            external_links += 1

                        if urlparse(link).netloc == domain and link not in visited:
                            visited.add(link)
                            new_links.append(link)

                    # Placeholder for LCP / performance / SEO
                    results.append({
                        "url": url,
                        "title": soup.title.string if soup.title else "N/A",
                        "html": html,
                        "internal_links_count": internal_links,
                        "external_links_count": external_links,
                        "broken_internal_links": broken_links,
                        "lcp_ms": None,  # To be filled by performance metrics
                        "top_competitor_score": None  # Placeholder for competitor comparison
                    })
            to_crawl.extend(new_links)
    return {"report": results}
