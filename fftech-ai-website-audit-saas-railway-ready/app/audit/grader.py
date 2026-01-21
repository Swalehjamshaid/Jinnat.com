from app.audit.crawler import crawl_site
from app.audit.performance import get_performance_metrics
from app.audit.links import check_links
import time

GRADE_BANDS = [(90,'A+'),(80,'A'),(70,'B'),(60,'C'),(0,'D')]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    penalties = 0
    penalties += onpage.get('missing_title_tags',0)*2
    penalties += onpage.get('missing_meta_descriptions',0)*1.5
    penalties += onpage.get('multiple_h1',0)*1
    penalties += links.get('total_broken_links',0)*0.5
    
    lcp = perf.get('lcp_ms', 4000) or 4000
    fcp = perf.get('fcp_ms', 2000) or 2000
    perf_score = max(0, 100 - (lcp/40 + fcp/30))
    
    coverage = min(100, crawl_pages_count*2)
    raw = max(0, 100-penalties)*0.5 + perf_score*0.3 + coverage*0.2
    overall = max(0, min(100, raw))
    
    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break
    return overall, grade, {'onpage': max(0, 100-penalties), 'performance': perf_score, 'coverage': coverage}

def run_audit(url: str):
    """
    The orchestrator function called by the API.
    It gathers data from crawler and performance modules, then computes the score.
    """
    # 1. Crawl the site
    crawl_results = crawl_site(url)
    
    # 2. Get Performance data
    perf_data = get_performance_metrics(url)
    
    # 3. Check links
    link_data = check_links(url)
    
    # 4. Compute final scores
    overall_score, grade, breakdown = compute_scores(
        onpage=crawl_results.get('onpage_stats', {}),
        perf=perf_data,
        links=link_data,
        crawl_pages_count=crawl_results.get('pages_crawled', 0)
    )
    
    return {
        "url": url,
        "overall_score": round(overall_score, 2),
        "grade": grade,
        "performance": breakdown['performance'],
        "onpage": breakdown['onpage'],
        "coverage": breakdown['coverage'],
        "timestamp": int(time.time()),
        "details": {
            "crawl": crawl_results,
            "performance": perf_data,
            "links": link_data
        }
    }
