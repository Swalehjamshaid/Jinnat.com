import asyncio
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

sem = asyncio.Semaphore(10)  # limit concurrent HEAD requests

async def check_link(client, link):
    async with sem:
        try:
            resp = await client.head(link, follow_redirects=True, timeout=3.0)
            return resp.status_code >= 400
        except (httpx.RequestError, httpx.TimeoutException):
            # Treat timeouts, DNS errors, connection issues as broken
            return True

async def analyze_links_async(html_input, base_url, progress_callback=None):
    if progress_callback:
        await progress_callback({"status": "🔗 Checking link integrity...", "crawl_progress": 75})

    page_url = next(iter(html_input))
    html = html_input[page_url]
    soup = BeautifulSoup(html or "", "html.parser")

    internal = set()
    external = set()
    warning_count = 0   # http:// links (internal or external)
    broken_count = 0

    domain = urlparse(base_url).netloc

    # Collect all links
    links = soup.find_all("a", href=True)
    
    if progress_callback:
        await progress_callback({
            "status": f"Found {len(links)} links – analyzing...",
            "crawl_progress": 78
        })

    for a in links:
        href = a["href"].split('#')[0].strip()
        if not href or href.startswith(("tel:", "mailto:", "javascript:", "#")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Skip invalid / empty schemes
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            continue

        # Count as warning if using plain http
        if parsed.scheme == "http":
            warning_count += 1

        if parsed.netloc == domain or not parsed.netloc:
            internal.add(full_url)
        else:
            external.add(full_url)

    # Check up to 20 internal links for broken status (increased from 10)
    to_check = list(internal)[:20]

    if progress_callback and to_check:
        await progress_callback({
            "status": f"Validating {len(to_check)} internal links...",
            "crawl_progress": 82
        })

    if to_check:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            tasks = [check_link(client, link) for link in to_check]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for r in results:
                if isinstance(r, Exception):
                    broken_count += 1
                elif r:
                    broken_count += 1

    healthy_count = len(internal) - broken_count  # approximate

    if progress_callback:
        await progress_callback({
            "status": f"Links analyzed: {len(internal)} internal, {len(external)} external",
            "crawl_progress": 95
        })

    return {
        "internal_links_count": len(internal),
        "external_links_count": len(external),
        "broken_internal_links": broken_count,
        "warning_links_count": warning_count,
        # Added for better chart mapping (Healthy = non-broken internal)
        "healthy_internal_links": healthy_count
    }
