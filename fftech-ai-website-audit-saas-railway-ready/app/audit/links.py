# app/audit/links.py
import asyncio
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

async def analyze_links_async(html_dict, base_url, callback=None):
    """
    Analyze links on a website:
    - Count internal links
    - Count external links
    - Identify broken links (status >= 400)
    """
    html = html_dict.get(base_url, "")
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    internal_links = []
    external_links = []
    broken_links = []

    async def check_link(link):
        # Convert relative URLs to absolute
        if not link.startswith("http"):
            link = urljoin(base_url, link)
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                r = await client.head(link)
                if r.status_code >= 400:
                    broken_links.append(link)
        except:
            broken_links.append(link)

    tasks = []
    for tag in links:
        href = tag["href"]
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != urlparse(base_url).netloc:
            external_links.append(href)
        else:
            internal_links.append(href)
        tasks.append(check_link(href))

    # Run async checks concurrently
    await asyncio.gather(*tasks, return_exceptions=True)

    result = {
        "internal_links_count": len(internal_links),
        "external_links_count": len(external_links),
        "broken_internal_links": len(broken_links),
        "broken_links_list": broken_links
    }

    if callback:
        await callback({"status": "🔗 Links analyzed", "crawl_progress": 70})

    return result
