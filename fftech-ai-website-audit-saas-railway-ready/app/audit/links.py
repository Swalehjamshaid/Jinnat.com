import asyncio
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

sem = asyncio.Semaphore(10)

async def check_link(client, link):
    async with sem:
        try:
            # HEAD request is faster for checking if a link is broken
            resp = await client.head(link, follow_redirects=True, timeout=3.0)
            return resp.status_code >= 400
        except:
            return True

async def analyze_links_async(html_input, base_url, progress_callback=None):
    if progress_callback:
        await progress_callback({"status": "🔗 Checking link integrity...", "crawl_progress": 75})
    
    page_url = next(iter(html_input))
    html = html_input[page_url]
    soup = BeautifulSoup(html, "html.parser")
    
    internal, external = set(), set()
    domain = urlparse(base_url).netloc
    
    for a in soup.find_all("a", href=True):
        href = a["href"].split('#')[0].strip()
        if not href or any(href.startswith(s) for s in ["tel:", "mailto:", "javascript:"]): 
            continue
        
        full_url = urljoin(base_url, href)
        if domain in urlparse(full_url).netloc:
            internal.add(full_url)
        else:
            external.add(full_url)

    # Validate first 10 internal links for the 'Broken' attribute
    to_check = list(internal)[:10]
    async with httpx.AsyncClient(verify=False) as client:
        tasks = [check_link(client, l) for l in to_check]
        results = await asyncio.gather(*tasks)
        broken_count = sum(1 for r in results if r)

    return {
        "internal_links_count": len(internal),
        "external_links_count": len(external),
        "broken_internal_links": broken_count
    }
