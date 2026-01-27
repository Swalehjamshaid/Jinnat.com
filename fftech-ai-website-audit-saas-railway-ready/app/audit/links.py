# app/audit/link.py
import asyncio
from typing import Dict, Set, Tuple, List
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "#")


def _is_skippable(href: str) -> bool:
    if not href:
        return True
    href = href.strip()
    return any(href.lower().startswith(s) for s in SKIP_SCHEMES)


def _same_site(netloc_a: str, netloc_b: str) -> bool:
    a = netloc_a.lower().lstrip("www.")
    b = netloc_b.lower().lstrip("www.")
    return a == b


def extract_links_from_html(html: str, base_url: str) -> Tuple[Set[str], Set[str]]:
    """
    Parse anchor tags from the HTML and split into internal/external sets.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    base = urlparse(base_url)

    internal: Set[str] = set()
    external: Set[str] = set()

    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if _is_skippable(href):
            continue

        # Resolve relative and protocol-relative URLs
        abs_url = urljoin(base_url, href)

        try:
            parsed = urlparse(abs_url)
        except Exception:
            continue

        if not parsed.scheme or not parsed.netloc:
            # invalid or incomplete
            continue

        if _same_site(parsed.netloc, base.netloc):
            internal.add(abs_url)
        else:
            external.add(abs_url)

    return internal, external


async def _check_link_status(
    client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore
) -> Tuple[str, bool]:
    """
    Returns (url, is_broken). We treat >=400 or network error as broken.
    Prefer HEAD; fall back to GET if HEAD not allowed.
    """
    async with semaphore:
        try:
            resp = await client.head(url, follow_redirects=True)
            if resp.status_code >= 400 or resp.status_code < 100:
                # Some servers don't support HEAD reliably, try GET once.
                resp2 = await client.get(url, follow_redirects=True)
                return url, resp2.status_code >= 400
            return url, False
        except Exception:
            return url, True


async def analyze_links_async(
    pages: Dict[str, str],
    base_url: str,
    callback,
    max_concurrency: int = 10,
    check_internal_broken: bool = True,
) -> Dict:
    """
    Analyze links for a set of pages (dict: url -> html). Primarily called with home page.
    Returns a dict shaped to feed your UI.

    Structure:
    {
        "internal_links_count": int,
        "external_links_count": int,
        "broken_internal_links": int,
        "broken_internal_samples": [.. up to 10 ..]
    }
    """
    try:
        await callback({"status": "🔗 Collecting links...", "crawl_progress": 60})
    except Exception:
        # Don't fail the whole pipeline if callback fails
        pass

    all_internal: Set[str] = set()
    all_external: Set[str] = set()

    for page_url, html in (pages or {}).items():
        internal, external = extract_links_from_html(html, page_url or base_url)
        all_internal |= internal
        all_external |= external

    broken_count = 0
    broken_samples: List[str] = []

    if check_internal_broken and all_internal:
        semaphore = asyncio.Semaphore(max_concurrency)
        async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
            tasks = [
                _check_link_status(client, url, semaphore)
                for url in sorted(all_internal)
            ]

            # Stream progress in batches
            total = len(tasks)
            completed = 0
            for coro in asyncio.as_completed(tasks):
                url, is_broken = await coro
                completed += 1
                if is_broken:
                    broken_count += 1
                    if len(broken_samples) < 10:
                        broken_samples.append(url)

                # Report progress occasionally
                if completed == total or completed % max(1, total // 5) == 0:
                    try:
                        await callback(
                            {
                                "status": f"🔎 Checking internal links ({completed}/{total})...",
                                "crawl_progress": min(90, 60 + int(30 * (completed / total))),
                            }
                        )
                    except Exception:
                        pass

    result = {
        "internal_links_count": len(all_internal),
        "external_links_count": len(all_external),
        "broken_internal_links": broken_count,
        "broken_internal_samples": broken_samples,
    }

    try:
        await callback({"status": "🔗 Link audit complete.", "crawl_progress": 90})
    except Exception:
        pass

    return result
