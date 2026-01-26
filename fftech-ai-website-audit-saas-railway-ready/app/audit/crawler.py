import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque

HEADERS = {
    "User-Agent": "FFTechAuditBot/5.0 (+https://fftech.ai/audit)"
}

ALLOWED_CONTENT_TYPES = ("text/html",)


def is_valid_html(response):
    ctype = response.headers.get("Content-Type", "")
    return any(ct in ctype for ct in ALLOWED_CONTENT_TYPES)


def normalize_url(base, link):
    link = link.split("#")[0].strip()
    if not link:
        return None
    return urljoin(base, link)


def crawl_site(start_url: str, max_pages=40, timeout=8):
    """
    Fast, safe, production-grade crawler
    Completes within 30–120 seconds
    """

    parsed = urlparse(start_url)
    domain = parsed.netloc

    visited = set()
    pages = []
    queue = deque([start_url])

    session = requests.Session()
    session.headers.update(HEADERS)

    start_time = time.time()
    MAX_RUNTIME = 90  # hard stop safety

    while queue and len(visited) < max_pages:
        if time.time() - start_time > MAX_RUNTIME:
            break

        url = queue.popleft()
        if url in visited:
            continue

        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            if response.status_code != 200:
                continue
            if not is_valid_html(response):
                continue
        except requests.RequestException:
            continue

        visited.add(url)

        soup = BeautifulSoup(response.text, "html.parser")

        page_data = {
            "url": url,
            "title": soup.title.string.strip() if soup.title else "",
            "meta_description": "",
            "h1": [],
            "images": [],
            "links": [],
            "html": response.text,
            "soup": soup,
        }

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            page_data["meta_description"] = meta_desc["content"].strip()

        # H1 tags
        page_data["h1"] = [h.get_text(strip=True) for h in soup.find_all("h1")]

        # Images (for accessibility audit)
        for img in soup.find_all("img"):
            page_data["images"].append({
                "src": img.get("src"),
                "alt": img.get("alt", "").strip()
            })

        # Links discovery
        for a in soup.select("a[href]"):
            link = normalize_url(url, a["href"])
            if not link:
                continue

            parsed_link = urlparse(link)

            page_data["links"].append({
                "url": link,
                "internal": parsed_link.netloc == domain
            })

            if parsed_link.netloc == domain and link not in visited:
                queue.append(link)

        pages.append(page_data)

    return {
        "start_url": start_url,
        "domain": domain,
        "pages_crawled": len(pages),
        "crawl_time_seconds": round(time.time() - start_time, 2),
        "pages": pages,
    }


__all__ = ["crawl_site"]
