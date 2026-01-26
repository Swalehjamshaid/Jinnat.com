
# app/audit/crawler.py
import logging
from collections import deque
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("audit_engine")

MAX_CONCURRENT_REQUESTS = 10  # Not used in this strict sync version; kept for compatibility
MAX_PAGES = 50
REQUEST_TIMEOUT = 10


def fetch_page_sync(client: httpx.Client, url: str):
    """
    Synchronous page fetcher.
    Returns: (html_text: str, status_code: int|None)
    """
    try:
        resp = client.get(url, timeout=REQUEST_TIMEOUT)
        return resp.text, resp.status_code
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return "", None


def analyze_seo(html: str):
    """
    Same as before: extract quick SEO stats from the HTML.
    """
    soup = BeautifulSoup(html, "lxml")

    # Images missing alt
    images = soup.find_all("img")
    images_missing_alt = sum(1 for img in images if not img.get("alt"))

    # Title & meta description
    title = soup.find("title")
    meta_desc = soup.find("meta", attrs={"name": "description"})

    return {
        "images_missing_alt": images_missing_alt,
        "title_missing": 0 if title and title.text.strip() else 1,
        "meta_description_missing": 0 if meta_desc and meta_desc.get("content") else 1,
    }


def crawl(
    start_url: str,
    max_pages: int = MAX_PAGES,
    progress_callback=None,
):
    """
    Synchronous crawler (no asyncio) with breadth-first traversal limited by `max_pages`.
    If provided, `progress_callback` will be called as:
        progress_callback({
            "crawl_progress": float,  # percentage (0..100)
            "status": str,
            "finished": bool
        })
    """

    parsed = urlparse(start_url)
    domain = parsed.netloc

    visited = set()
    internal_links = set()
    external_links = set()
    broken_internal = set()
    broken_external = set()
    results = []

    # Simple FIFO queue for URLs to visit
    queue = deque([start_url])

    with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        while queue and len(visited) < max_pages:
            url = queue.popleft()

            if url in visited:
                continue

            visited.add(url)

            html, status = fetch_page_sync(client, url)

            seo_data = {"images_missing_alt": 0, "title_missing": 0, "meta_description_missing": 0}

            if not status or status >= 400:
                if domain in urlparse(url).netloc:
                    broken_internal.add(url)
                else:
                    broken_external.add(url)
            else:
                # Parse and collect links only when OK
                seo_data = analyze_seo(html)

                soup = BeautifulSoup(html, "lxml")
                for tag in soup.find_all("a", href=True):
                    link = urljoin(url, tag.get("href"))
                    # Normalize by stripping fragments
                    parsed_link = urlparse(link)
                    normalized_link = parsed_link._replace(fragment="").geturl()

                    link_domain = parsed_link.netloc

                    if link_domain == domain:
                        # internal
                        if normalized_link not in visited and normalized_link not in internal_links:
                            internal_links.add(normalized_link)
                            # Only queue http/https pages (skip mailto:, tel:, etc.)
                            if parsed_link.scheme in ("http", "https"):
                                queue.append(normalized_link)
                    else:
                        # external
                        external_links.add(normalized_link)

            results.append({
                "url": url,
                "status": status or "failed",
                "seo": seo_data,
            })

            # Synchronous progress reporting
            if progress_callback:
                try:
                    progress_callback({
                        "crawl_progress": round(len(visited) / float(max_pages) * 100.0, 2),
                        "status": f"Crawled {len(visited)} pages...",
                        "finished": False
                    })
                except Exception as e:
                    logger.debug(f"Progress callback failed: {e}")

    # Final aggregation
    report = {
        "unique_internal": len(internal_links),
        "unique_external": len(external_links),
        "broken_internal": len(broken_internal),
        "broken_external": len(broken_external),
        "crawled_count": len(visited),
        "total_images_missing_alt": sum(r["seo"]["images_missing_alt"] for r in results),
        "total_titles_missing": sum(r["seo"]["title_missing"] for r in results),
        "total_meta_description_missing": sum(r["seo"]["meta_description_missing"] for r in results),
        "pages": results
    }

    if progress_callback:
        try:
            progress_callback({
                "crawl_progress": 100.0,
                "status": f"Finished. Crawled {len(visited)} pages.",
                "finished": True
            })
        except Exception as e:
            logger.debug(f"Progress callback failed at completion: {e}")

    return report
