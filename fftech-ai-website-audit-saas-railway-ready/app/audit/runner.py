# app/audit/runner.py
import logging, time
from typing import Dict
from urllib.parse import urlparse
import certifi, requests
from bs4 import BeautifulSoup
import urllib3
from .crawler import crawl  # Updated crawler

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('audit_engine')

def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(v))))

def run_audit(url: str) -> Dict:
    """
    Fast Web Audit – SEO, Performance, Links
    Optimized to finish under 1 minute
    """
    logger.info("RUNNING AUDIT FOR URL: %s", url)
    start_time = time.time()
    headers = {'User-Agent':'FFTech-AuditBot/4.0','Accept':'text/html,application/xhtml+xml'}
    session = requests.Session()
    session.headers.update(headers)

    ssl_verified = True
    try:
        response = session.get(url, timeout=15, verify=certifi.where(), allow_redirects=True)
    except requests.exceptions.SSLError:
        ssl_verified = False
        response = session.get(url, timeout=15, verify=False, allow_redirects=True)
    except Exception as e:
        raise RuntimeError(f"Cannot fetch URL {url}: {e}")

    load_time = round(time.time() - start_time, 2)
    final_url = response.url
    parsed = urlparse(final_url)
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # ---------------- SEO ----------------
    title = soup.title.string.strip() if soup.title else ""
    meta_desc = (soup.find("meta", {"name":"description"}) or {}).get("content", "").strip()
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)
    img_tags = soup.find_all("img")
    missing_alt = sum(1 for img in img_tags if not img.get("alt"))

    seo_issues = []
    seo_score = 0

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

    # ---------------- Performance ----------------
    page_size_kb = round(len(html.encode("utf-8"))/1024,2)
    perf_score = 100 - min(40, load_time*8) - min(40, page_size_kb/30)
    perf_score = _clamp(perf_score)
    speed_sub = _clamp(100-min(100, load_time*25))
    weight_sub = _clamp(100-min(100, (page_size_kb/2000)*100))
    perf_issues = []
    if load_time>3: perf_issues.append(f"Slow load {load_time}s")
    if page_size_kb>2000: perf_issues.append(f"Large page {page_size_kb}KB")

    # ---------------- Crawl ----------------
    crawl_res = crawl(final_url, max_pages=20, delay=0.05)  # optimized
    internal_total = crawl_res.unique_internal
    external_total = crawl_res.unique_external
    broken_count = len(crawl_res.broken_internal)
    broken_external_count = len(crawl_res.broken_external)

    coverage_base = min(60, internal_total*2) + min(30, external_total)
    broken_penalty = min(20, broken_count*2 + broken_external_count)
    coverage_score = _clamp(coverage_base - broken_penalty)
    coverage_issues = []
    if internal_total<5: coverage_issues.append(f"Low internal links {internal_total}")
    if external_total<2: coverage_issues.append(f"Low external links {external_total}")
    if broken_count>0: coverage_issues.append(f"Broken internal links {broken_count}")
    if broken_external_count>0: coverage_issues.append(f"Broken external links {broken_external_count}")

    internal_sub = _clamp(min(100, internal_total*5))
    external_sub = _clamp(min(100, external_total*3))

    # ---------------- Overall Score ----------------
    overall_score = _clamp(seo_score*0.45 + perf_score*0.35 + coverage_score*0.20)
    grade = "A" if overall_score>=85 else "B" if overall_score>=70 else "C" if overall_score>=55 else "D"
    confidence = overall_score

    chart_data = {
        "bar": {
            "labels":["SEO","Speed","Links","Trust","Images","Meta"],
            "data":[seo_score, perf_score, coverage_score, confidence, _clamp(100-missing_alt), _clamp(len(meta_desc))],
            "colors":["#0d6efd","#20c997","#ffc107","#dc3545","#6f42c1","#fd7e14"]
        }
    }

    return {
        "finished": True,
        "url": final_url,
        "domain": parsed.netloc,
        "http_status": response.status_code,
        "https": parsed.scheme=="https",
        "ssl_secure": ssl_verified,
        "overall_score": overall_score,
        "grade": grade,
        "breakdown": {"onpage":seo_score,"performance":perf_score,"coverage":coverage_score,"confidence":confidence},
        "metrics": {
            "title_length":len(title),
            "meta_description_length":len(meta_desc),
            "h1_count":h1_count,
            "internal_links":internal_total,
            "external_links":external_total,
            "broken_internal_links":broken_count,
            "broken_external_links":broken_external_count,
            "load_time_sec":load_time,
            "page_size_kb":page_size_kb,
            "pages_crawled":crawl_res.crawled_count,
            "crawl_time_sec":crawl_res.total_crawl_time,
            "images_missing_alt":missing_alt
        },
        "issues": {"seo":seo_issues,"performance":perf_issues,"coverage":coverage_issues},
        "status":"Audit completed successfully"
    }
