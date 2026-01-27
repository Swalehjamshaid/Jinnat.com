import asyncio
import logging
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("audit_engine")

async def check_single_link(client: httpx.AsyncClient, link: str) -> bool:
    """Returns True if the link is broken (4xx or 5xx), False otherwise."""
    try:
        # Use HEAD request for speed; it doesn't download the whole page body
        resp = await client.head(link, follow_redirects=True, timeout=5.0)
        return resp.status_code >= 400
    except Exception:
        # If the request fails (timeout, DNS error), we treat it as broken
        return True

async def extract_links_from_html(html: str, base_url: str) -> Dict[str, int]:
    """Extract and classify links and verify if internal ones are broken."""
    if not html.strip():
        return {
            "internal_links_count": 0,
            "external_links_count": 0,
            "broken_internal_links": 0,
            "warning_links_count": 0
        }

    soup = BeautifulSoup(html, "html.parser")
    internal = set()
    external = set()
    warnings = set()

    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc.lower()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "tel:", "mailto:")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if not parsed.scheme or not parsed.netloc:
            warnings.add(full_url)
            continue

        domain = parsed.netloc.lower()
        if domain == base_domain or domain.endswith("." + base_domain):
            internal.add(full_url)
        else:
            external.add(full_url)

    # --- REAL BROKEN LINK CHECKER ---
    broken_internal_count = 0
    if internal:
        async with httpx.AsyncClient(verify=False) as client:
            # We check the first 20 internal links to maintain speed
            tasks = [check_single_link(client, link) for link in list(internal)[:20]]
            results = await asyncio.gather(*tasks)
            broken_internal_count = sum(1 for is_broken in results if is_broken)

    return {
        "internal_links_count": len(internal),
        "external_links_count": len(external),
        "broken_internal_links": broken_internal_count,
        "warning_links_count": len(warnings)
    }

# analyze_links_async remains the same as your provided code
