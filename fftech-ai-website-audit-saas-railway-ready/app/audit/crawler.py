import asyncio
import httpx
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup

# -------------------------
# Configuration
# -------------------------
MAX_PAGES = 20
CONCURRENCY = 10
TIMEOUT = 7.0

HEADERS = {
    "User-Agent": "FFTechAuditBot/1.0",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# -------------------------
# Helpers
# -------------------------
def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)          # remove #fragment
    parsed = urlparse(url)
    clean = parsed._replace(query="").geturl()
    return clean.rstrip("/")

# -------------------------
# Fetch Page
# -------------------------
async def fast_fetch(client: httpx.AsyncClient, url: str):
    try:
        resp = await client.get(url, headers=HEADERS, timeout=TIMEOUT)
        if "text/html" not in resp.headers.get("content-type", ""):
            return "", 0
        return resp.text, resp.status_code
    except Exception:
        return "", 0

# -------------------------
# Crawl Website
# -------------------------
async def crawl(start_url: str, max_pages: int = MAX_PAGES):
    domain = urlparse(start_url).netloc

    visited = set()
    to_crawl = [normalize_url(start_url)]
    results = []

    limits = httpx.Limits(
        max_connections=CONCURRENCY,
        max_keepalive_connections=5
    )

    async with httpx.AsyncClient(
        limits=limits,
        follow_redirects=True,
        headers=HEADERS
    ) as client:

        while to_crawl and len(results) < max_pages:
            batch = to_crawl[:CONCURRENCY]
            to_crawl = to_crawl[CONCURRENCY:]

            tasks = [fast_fetch(client, url) for url in batch]
            responses = await asyncio.gather(*tasks)

            for i, (html, status) in enumerate(responses):
                url = batch[i]
                if url in visited or status != 200 or not html:
                    continue

                visited.add(url)

                soup = BeautifulSoup(html, "lxml")

                results.append({
                    "url": url,
                    "title": soup.title.string.strip() if soup.title else "N/A",
                    "html": html
                })

                if len(results) >= max_pages:
                    break

                for a in soup.find_all("a", href=True):
                    link = normalize_url(urljoin(url, a["href"]))

                    if (
                        link.startswith("http")
                        and urlparse(link).netloc == domain
                        and link not in visited
                        and link not in to_crawl
                    ):
                        to_crawl.append(link)

    return {"report": results}
