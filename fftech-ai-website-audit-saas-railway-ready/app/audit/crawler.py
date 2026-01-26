import asyncio
import logging
import httpx
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Callable

logger = logging.getLogger("audit_engine")

# SaaS Speed Settings
MAX_PAGES = 15         
CONCURRENCY = 10      
TIMEOUT = 5.0         

async def fast_fetch(client: httpx.AsyncClient, url: str):
    try:
        # SSL verify=False is critical for performance and bypassing regional cert issues
        resp = await client.get(url, timeout=TIMEOUT)
        return resp.text, resp.status_code
    except Exception:
        return "", 0

async def crawl(start_url: str, max_pages: int = MAX_PAGES):
    """
    High-speed crawler that returns a list of dictionaries.
    """
    domain = urlparse(start_url).netloc
    visited = {start_url}
    to_crawl = [start_url]
    results = []
    
    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=5)
    async with httpx.AsyncClient(verify=False, limits=limits, follow_redirects=True) as client:
        
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
                    
                    # Store Result - 'html' key is CRITICAL for seo.py
                    results.append({
                        "url": url, 
                        "title": soup.title.string if soup.title else "N/A",
                        "html": html 
                    })
                    
                    if len(results) + len(to_crawl) < max_pages:
                        for a in soup.find_all("a", href=True):
                            link = urljoin(url, a["href"])
                            if urlparse(link).netloc == domain and link not in visited:
                                visited.add(link)
                                new_links.append(link)
            
            to_crawl.extend(new_links)

    return {"report": results}
