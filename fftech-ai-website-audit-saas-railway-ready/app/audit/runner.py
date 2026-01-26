# app/audit/runner.py
import logging, time, asyncio
from typing import Dict
from urllib.parse import urlparse
import certifi
import httpx
from bs4 import BeautifulSoup
from .crawler import async_crawl  # New async crawler for high-speed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('audit_engine')

def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(v))))

async def fetch_html(url: str) -> Dict:
    """Fetch HTML asynchronously and measure load time."""
    headers = {'User-Agent': 'FFTech-AuditBot/5.0', 'Accept': 'text/html,application/xhtml+xml'}
    start_time = time.time()
    async with httpx.AsyncClient(timeout=20, verify=certifi.where(), headers=headers, follow_redirects=True) as client:
        resp = await client.get(url)
        html = resp.text
        final_url = str(resp.url)
        status_code = resp.status_code
        load_time = round(time.time() - start_time, 2)
    return {"html": html, "final_url": final_url, "status": status_code, "load_time": load_time}

async def analyze_page(url: str) -> Dict:
    """Analyze a single page for SEO and performance."""
    page_data = await fetch_html(url)
    soup = BeautifulSoup(page_data["html"], "lxml")

    title = soup.title.string.strip() if soup.title else ""
    meta_desc = (soup.find("meta", {"name":"description"}) or {}).get("content", "").strip()
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)
    img_tags = soup.find_all("img")
    missing_alt = sum(1 for img in img_tags if not img.get("alt"))

    seo_score = 0
    seo_issues = []

    if title:
        seo_score += 25 + max(0, 25 - abs(len(title)-55))
        if len(title)<25: seo_issues.append("Title very short")
        elif len(title)>65: seo_issues.append("Title too long")
    else:
        seo_issues.append("Missing title")

    if meta_desc:
        seo_score += min(25,len(meta_desc)/6)
        if len(meta_desc)<80: seo_issues.append("Meta description short")
        elif len(meta_desc)>180: seo_issues.append("Meta description long")
    else:
        seo_issues.append("Missing meta description")

    if h1_count==1:
        seo_score+=15
    elif h1_count==0:
        seo_issues.append("No H1")
    else:
        seo_issues.append(f"{h1_count} H1 tags")

    if missing_alt>0:
        seo_issues.append(f"{missing_alt} images missing alt")
    seo_score = _clamp(seo_score)

    perf_score = 100
    page_size_kb = round(len(page_data["html"].encode("utf-8"))/1024,2)
    perf_score -= min(40, page_data["load_time"]*8)
    perf_score -= min(40, page_size_kb/30)
    perf_score = _clamp(perf_score)

    return {
        "final_url": page_data["final_url"],
        "domain": urlparse(page_data["final_url"]).netloc,
        "http_status": page_data["status"],
        "seo_score": seo_score,
        "seo_issues": seo_issues,
        "perf_score": perf_score,
        "load_time": page_data["load_time"],
        "page_size_kb": page_size_kb,
        "missing_alt": missing_alt,
        "meta_desc_length": len(meta_desc),
        "h1_count": h1_count
    }

async def run_audit_ws(url: str, websocket=None, max_pages: int = 15) -> Dict:
    """Runs audit with real-time WebSocket progress."""
    start_time = time.time()
    if websocket:
        await websocket.send_json({"status": "started", "message": f"Starting audit for {url}"})

    # Crawl site asynchronously
    crawl_res = await async_crawl(url, max_pages=max_pages, websocket=websocket)

    # Homepage analysis
    page_data = await analyze_page(url)
    if websocket:
        await websocket.send_json({"status": "homepage_done", "message": "Homepage analysis complete", "data": page_data})

    # Coverage/Links scoring
    internal_total = crawl_res["unique_internal"]
    external_total = crawl_res["unique_external"]
    broken_count = crawl_res["broken_internal"]
    broken_external_count = crawl_res["broken_external"]

    coverage_base = min(60, internal_total*2) + min(30, external_total)
    broken_penalty = min(20, broken_count*2 + broken_external_count)
    coverage_score = _clamp(coverage_base - broken_penalty)
    coverage_issues = []
    if internal_total<5: coverage_issues.append(f"Low internal links {internal_total}")
    if external_total<2: coverage_issues.append(f"Low external links {external_total}")
    if broken_count>0: coverage_issues.append(f"Broken internal links {broken_count}")
    if broken_external_count>0: coverage_issues.append(f"Broken external links {broken_external_count}")

    overall_score = _clamp(
        page_data["seo_score"]*0.45 +
        page_data["perf_score"]*0.35 +
        coverage_score*0.20
    )
    grade = "A" if overall_score>=85 else "B" if overall_score>=70 else "C" if overall_score>=55 else "D"
    audit_time = round(time.time() - start_time, 2)

    result = {
        "finished": True,
        "url": page_data["final_url"],
        "domain": page_data["domain"],
        "http_status": page_data["http_status"],
        "overall_score": overall_score,
        "grade": grade,
        "audit_time_sec": audit_time,
        "breakdown": {
            "seo": page_data["seo_score"],
            "performance": page_data["perf_score"],
            "coverage": coverage_score
        },
        "issues": {
            "seo": page_data["seo_issues"],
            "coverage": coverage_issues
        },
        "metrics": {
            "load_time": page_data["load_time"],
            "page_size_kb": page_data["page_size_kb"],
            "missing_alt": page_data["missing_alt"],
            "meta_desc_length": page_data["meta_desc_length"],
            "h1_count": page_data["h1_count"],
            "internal_links": internal_total,
            "external_links": external_total,
            "broken_internal_links": broken_count,
            "broken_external_links": broken_external_count
        },
        "status": "Audit completed successfully"
    }

    if websocket:
        await websocket.send_json({"status": "completed", "message": "Audit completed", "data": result})
    return result
