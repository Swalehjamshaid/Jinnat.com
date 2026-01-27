# app/audit/crawler.py
import asyncio
import httpx
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

MAX_PAGES = 50
CONCURRENCY = 10
TIMEOUT = 10.0  # Increased timeout for slower pages

async def fast_fetch(client: httpx.AsyncClient, url: str):
    """Fetch a URL asynchronously"""
    try:
        resp = await client.get(url, timeout=TIMEOUT, follow_redirects=True, verify=False)
        return resp.text, resp.status_code
    except Exception:
        return "", 0

def categorize_links(base_domain: str, links: list):
    """Categorize links as internal, external, and broken"""
    internal, external, broken = 0, 0, 0
    for link in links:
        parsed = urlparse(link)
        if not parsed.netloc:
            continue
        if parsed.netloc == base_domain:
            internal += 1
        else:
            external += 1
        # For broken check, we could optionally ping here (or do in runner)
        # Currently, broken = 0 as placeholder
    return internal, external, broken

async def crawl(start_url: str, max_pages: int = MAX_PAGES):
    """Async crawl starting from start_url"""
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
                if status == 200 and html:
                    soup = BeautifulSoup(html, "lxml")
                    page_links = [urljoin(url, a['href']) for a in soup.find_all("a", href=True)]
                    internal, external, broken = categorize_links(domain, page_links)

                    # Placeholder for LCP / Performance metrics (update in runner)
                    lcp_ms = None  # Replace with real metric later

                    # Placeholder for competitor comparison
                    top_competitor_score = None  # Replace with real comparison logic

                    results.append({
                        "url": url,
                        "title": soup.title.string if soup.title else "N/A",
                        "html": html,
                        "internal_links_count": internal,
                        "external_links_count": external,
                        "broken_internal_links": broken,
                        "lcp_ms": lcp_ms,
                        "top_competitor_score": top_competitor_score,
                    })

                    if len(results) + len(to_crawl) < max_pages:
                        for link in page_links:
                            parsed_link = urlparse(link)
                            if parsed_link.netloc == domain and link not in visited:
                                visited.add(link)
                                new_links.append(link)
            to_crawl.extend(new_links)
    return {"report": results}
