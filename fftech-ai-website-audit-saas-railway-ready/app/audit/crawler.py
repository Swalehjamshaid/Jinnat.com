import asyncio
import logging
import httpx
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Callable

logger = logging.getLogger("audit_engine")

# SaaS Speed Settings - Optimized for International Response Times
MAX_PAGES = 15         
CONCURRENCY = 15      # Increased concurrency
TIMEOUT = 4.0         # Even tighter timeout for SaaS snappiness

async def async_crawl(start_url: str, max_pages: int = MAX_PAGES, progress_callback: Optional[Callable] = None):
    domain = urlparse(start_url).netloc
    visited = {start_url}
    results = []
    queue = asyncio.Queue()
    await queue.put(start_url)
    
    # Semaphore prevents hitting a site too hard while maintaining speed
    sem = asyncio.Semaphore(CONCURRENCY)
    
    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=20)
    async with httpx.AsyncClient(verify=False, limits=limits, follow_redirects=True, timeout=TIMEOUT) as client:
        
        async def process_url():
            while len(results) < max_pages:
                try:
                    # Non-blocking get from queue
                    current_url = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    break

                async with sem:
                    try:
                        resp = await client.get(current_url)
                        if resp.status_code == 200:
                            # Instant parsing with LXML
                            soup = BeautifulSoup(resp.text, "lxml")
                            
                            page_data = {
                                "url": current_url,
                                "title": soup.title.string[:50] if soup.title else "N/A"
                            }
                            results.append(page_data)

                            # Link Extraction
                            for a in soup.find_all("a", href=True):
                                link = urljoin(current_url, a["href"])
                                p_link = urlparse(link)
                                clean_link = f"{p_link.scheme}://{p_link.netloc}{p_link.path}"
                                
                                if p_link.netloc == domain and clean_link not in visited:
                                    visited.add(clean_link)
                                    await queue.put(clean_link)
                        
                        if progress_callback:
                            await progress_callback({"count": len(results), "status": "crawling"})
                            
                    except Exception as e:
                        logger.debug(f"Fast skip: {current_url}")
                    finally:
                        queue.task_done()

        # Fire off multiple workers that run independently
        workers = [asyncio.create_task(process_url()) for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)

    return {"total": len(results), "pages": results}
