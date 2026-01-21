import asyncio
from collections import deque
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from typing import Dict, Any, List, Set, Optional

import httpx
from bs4 import BeautifulSoup

from ..config import settings

DEFAULT_USER_AGENT = settings.USER_AGENT or 'FFTech-AI-Auditor/1.0 (+https://fftech.ai; contact@fftech.ai)'
DEFAULT_HEADERS = {'User-Agent': DEFAULT_USER_AGENT}

# Limit concurrent requests to avoid blocks / rate-limits
MAX_CONCURRENT_REQUESTS = 5


async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """
    Fetch a single page with timeout, retries, and structured data extraction.
    """
    async with semaphore:
        try:
            resp = await client.get(url, headers=DEFAULT_HEADERS, timeout=15.0, follow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return {
                    'url': url,
                    'status': resp.status_code,
                    'headers': dict(resp.headers),
                    'error': 'Non-HTML content',
                    'html': '',
                    'title': '',
                    'meta_desc': '',
                    'canonical': '',
                    'robots_meta': '',
                    'h1_count': 0,
                    'img_count': 0,
                    'internal_links': 0,
                    'external_links': 0,
                }

            html = resp.text
            soup = BeautifulSoup(html, 'lxml')

            # Extract useful SEO elements
            title = soup.title.string.strip() if soup.title else ''
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_desc = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else ''

            canonical = soup.find('link', rel='canonical')
            canonical = canonical['href'] if canonical else ''

            robots_meta = soup.find('meta', attrs={'name': 'robots'})
            robots_meta = robots_meta['content'].lower() if robots_meta else ''

            h1_count = len(soup.find_all('h1'))
            img_count = len(soup.find_all('img'))

            # Count links (internal vs external)
            internal = 0
            external = 0
            base_netloc = urlparse(url).netloc
            for a in soup.find_all('a', href=True):
                href = urljoin(url, a['href'])
                parsed = urlparse(href)
                if parsed.scheme in ('http', 'https'):
                    if parsed.netloc == base_netloc or parsed.netloc == 'www.' + base_netloc:
                        internal += 1
                    else:
                        external += 1

            return {
                'url': url,
                'status': resp.status_code,
                'headers': dict(resp.headers),
                'html': html,
                'title': title,
                'meta_desc': meta_desc,
                'canonical': canonical,
                'robots_meta': robots_meta,
                'h1_count': h1_count,
                'img_count': img_count,
                'internal_links': internal,
                'external_links': external,
            }

        except httpx.TimeoutException:
            return {'url': url, 'status': 0, 'error': 'Timeout'}
        except httpx.RequestError as e:
            return {'url': url, 'status': 0, 'error': f'Connection error: {str(e)}'}
        except Exception as e:
            return {'url': url, 'status': 0, 'error': str(e)}


async def is_allowed_by_robots(url: str, user_agent: str) -> bool:
    """Basic robots.txt check."""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(robots_url)
            if resp.status_code != 200:
                return True  # No robots.txt → allowed
            rp = RobotFileParser()
            rp.parse(resp.text.splitlines())
            return rp.can_fetch(user_agent, url)
    except:
        return True  # Fail open


async def crawl_site(
    start_url: str,
    max_pages: int = 50,
    max_depth: int = 5,
    respect_robots: bool = True,
    include_subdomains: bool = False
) -> List[Dict[str, Any]]:
    """
    Improved async web crawler for SEO audit.
    - BFS crawling with depth limit
    - Concurrent requests with semaphore
    - Robots.txt respect
    - Rich page metadata extraction
    """
    if respect_robots and not await is_allowed_by_robots(start_url, DEFAULT_USER_AGENT):
        raise ValueError(f"Crawling disallowed by robots.txt for {start_url}")

    parsed_start = urlparse(start_url)
    base_netloc = parsed_start.netloc
    base_domain = base_netloc.replace('www.', '')

    visited: Set[str] = set()
    to_visit: deque = deque([(start_url, 0)])  # (url, depth)
    pages: List[Dict[str, Any]] = []

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async with httpx.AsyncClient(follow_redirects=True, http2=True) as client:
        while to_visit and len(pages) < max_pages:
            url, depth = to_visit.popleft()
            if url in visited or depth > max_depth:
                continue
            visited.add(url)

            page = await fetch_page(client, url, semaphore)
            pages.append(page)

            # Small delay to be polite
            await asyncio.sleep(0.3)

            html = page.get('html', '')
            if not html:
                continue

            soup = BeautifulSoup(html, 'lxml')

            for a in soup.find_all('a', href=True):
                href = urljoin(url, a['href'].strip())
                parsed = urlparse(href)

                if parsed.scheme not in ('http', 'https'):
                    continue

                # Domain filtering
                target_netloc = parsed.netloc.replace('www.', '')
                if include_subdomains:
                    if target_netloc != base_domain:
                        continue
                else:
                    if parsed.netloc != base_netloc:
                        continue

                full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if full_url not in visited and full_url not in [u[0] for u in to_visit]:
                    if respect_robots and not await is_allowed_by_robots(full_url, DEFAULT_USER_AGENT):
                        continue
                    to_visit.append((full_url, depth + 1))

    return pages
