# app/audit/runner.py
# (exactly the same code you provided – no modifications)
import logging
import time
from typing import Dict, List
from urllib.parse import urlparse, urljoin
import certifi
import requests
from bs4 import BeautifulSoup
import urllib3
from .crawler import crawl
# Disable SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger('audit_engine')
def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(v))))
def run_audit(url: str) -> Dict:
    """Main single-URL audit orchestrator used by FastAPI SSE endpoint.
    Steps:
      1) Fetch landing page
      2) Compute SEO + Perf scores using DOM & timing
      3) Crawl site (same host) to compute coverage & link health
      4) Aggregate overall score, grade, and chart-ready data
    Returns a dict consumed by index.html JS (tiles + charts)
    """
    logger.info('RUNNING AUDIT FOR URL: %s', url)
    start_time = time.time()
    headers = {
        'User-Agent': 'FFTech-AuditBot/2.1 (+https://fftech.audit)',
        'Accept': 'text/html,application/xhtml+xml',
    }
    session = requests.Session()
    session.headers.update(headers)
    ssl_verified = True
    try:
        response = session.get(url, timeout=20, verify=certifi.where(), allow_redirects=True)
    except requests.exceptions.SSLError:
        logger.warning('SSL error on %s – falling back to unverified.', url)
        ssl_verified = False
        response = session.get(url, timeout=20, verify=False, allow_redirects=True)
    except requests.RequestException as e:
        raise RuntimeError(f'Failed to fetch URL {url}: {e}')
    load_time = round(time.time() - start_time, 2)
    final_url = response.url
    parsed = urlparse(final_url)
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    # SEO scoring + issues
    title = soup.title.string.strip() if soup.title and soup.title.string else ''
    meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
    meta_desc = meta_desc_tag['content'].strip() if meta_desc_tag and meta_desc_tag.get('content') else ''
    h1_tags = soup.find_all('h1')
    h1_count = len(h1_tags)
    seo_issues: List[str] = []
    seo_score = 0.0
    if title:
        seo_score += 25
        title_bonus = max(0.0, 25 - abs(len(title) - 55))
        seo_score += title_bonus
        if len(title) < 25:
            seo_issues.append('Title is very short (<25 chars)')
        elif len(title) > 65:
            seo_issues.append('Title is long (>65 chars)')
    else:
        seo_issues.append('Missing <title> tag')
    if meta_desc:
        seo_score += min(25.0, len(meta_desc) / 6.0)
        if len(meta_desc) < 80:
            seo_issues.append('Meta description is short (<80 chars)')
        elif len(meta_desc) > 180:
            seo_issues.append('Meta description is long (>180 chars)')
    else:
        seo_issues.append('Missing meta description')
    if h1_count == 1:
        seo_score += 15
    elif h1_count == 0:
        seo_issues.append('No H1 tag found')
    else:
        seo_issues.append('Multiple H1 tags found')
    seo_score = _clamp(seo_score)
    # Performance scoring + issues
    page_size_kb = round(len(html.encode('utf-8')) / 1024, 2)
    perf_issues: List[str] = []
    perf_score = 100
    perf_score -= min(40, load_time * 8) # penalty for slow pages
    perf_score -= min(40, page_size_kb / 30) # penalty for large pages
    perf_score = _clamp(perf_score)
    if load_time > 3.0:
        perf_issues.append(f'Slow page load ({load_time}s > 3s)')
    if page_size_kb > 2000:
        perf_issues.append(f'Large page size ({page_size_kb} KB > 2000 KB)')
    # Sub-metrics for radar
    speed_sub = _clamp(100 - min(100, load_time * 25))
    weight_sub = _clamp(100 - min(100, (page_size_kb / 2000) * 100))
    # Coverage via crawler
    crawl_res = crawl(final_url, max_pages=20, delay=0.35)
    internal_total = crawl_res.unique_internal
    external_total = crawl_res.unique_external
    broken_count = len(crawl_res.broken_internal)
    coverage_base = min(60, internal_total * 2) + min(30, external_total)
    broken_penalty = min(20, broken_count * 2)
    coverage_score = _clamp(coverage_base - broken_penalty)
    coverage_issues: List[str] = []
    if internal_total < 5:
        coverage_issues.append(f'Low internal links ({internal_total} < 5)')
    if external_total < 2:
        coverage_issues.append(f'Low external links ({external_total} < 2)')
    if broken_count > 0:
        coverage_issues.append(f'Broken internal links: {broken_count}')
    internal_linking_sub = _clamp(min(100, internal_total * 5))
    external_linking_sub = _clamp(min(100, external_total * 3))
    overall_score = _clamp(
        seo_score * 0.45 +
        perf_score * 0.35 +
        coverage_score * 0.20
    )
    grade = (
        'A' if overall_score >= 85 else
        'B' if overall_score >= 70 else
        'C' if overall_score >= 55 else
        'D'
    )
    confidence_score = overall_score
    chart_data = {
        'bar': {
            'labels': ['SEO', 'Speed', 'Links', 'Trust'],
            'data': [seo_score, perf_score, coverage_score, confidence_score],
            'colors': ['#0d6efd', '#20c997', '#ffc107', '#dc3545'],
        },
        'radar': {
            'labels': [
                'Title Quality', 'Meta Description', 'H1 Structure',
                'Speed', 'Page Weight', 'Internal Linking', 'External Linking'
            ],
            'data': [
                _clamp(100 if title else 0),
                _clamp(100 if meta_desc else 0),
                _clamp(100 if h1_count == 1 else 50 if h1_count > 1 else 0),
                speed_sub,
                weight_sub,
                internal_linking_sub,
                external_linking_sub,
            ],
        },
        'doughnut': {
            'labels': ['SEO issues', 'Performance issues', 'Links issues'],
            'data': [len(seo_issues), len(perf_issues), len(coverage_issues)],
            'colors': ['#6f42c1', '#fd7e14', '#0dcaf0'],
        },
        'crawl': {
            'status_counts': dict(crawl_res.status_counts),
            'internal_total': internal_total,
            'external_total': external_total,
            'broken_internal': broken_count,
        }
    }
    return {
        'finished': True,
        'url': final_url,
        'domain': parsed.netloc,
        'http_status': response.status_code,
        'https': parsed.scheme == 'https',
        'ssl_secure': ssl_verified,
        'overall_score': overall_score,
        'grade': grade,
        'breakdown': {
            'onpage': seo_score,
            'performance': perf_score,
            'coverage': coverage_score,
            'confidence': confidence_score,
        },
        'metrics': {
            'title_length': len(title),
            'meta_description_length': len(meta_desc),
            'h1_count': h1_count,
            'internal_links': internal_total,
            'external_links': external_total,
            'broken_internal_links': broken_count,
            'load_time_sec': load_time,
            'page_size_kb': page_size_kb,
            'pages_crawled': crawl_res.crawled_count,
            'crawl_time_sec': crawl_res.total_crawl_time,
        },
        'issues': {
            'seo': seo_issues,
            'performance': perf_issues,
            'coverage': coverage_issues,
        },
        'issues_count': {
            'seo': len(seo_issues),
            'performance': len(perf_issues),
            'coverage': len(coverage_issues),
        },
        'chart_data': chart_data,
        'status': 'Audit completed successfully',
    }
