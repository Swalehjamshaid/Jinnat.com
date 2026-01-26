import requests, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque

HEADERS = {"User-Agent": "FFTechAuditBot/5.0"}

def crawl_site(start_url: str, max_pages=40, timeout=8):
    domain = urlparse(start_url).netloc
    visited, pages = set(), []
    queue = deque([start_url])

    start_time = time.time()

    while queue and len(visited) < max_pages and time.time() - start_time < 90:
        url = queue.popleft()
        if url in visited:
            continue

        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
        except:
            continue

        visited.add(url)
        pages.append({"url": url, "soup": soup, "html": r.text})

        for a in soup.select("a[href]"):
            link = urljoin(url, a["href"].split("#")[0])
            if urlparse(link).netloc == domain and link not in visited:
                queue.append(link)

    return {
        "pages": pages,
        "pages_crawled": len(pages)
    }
