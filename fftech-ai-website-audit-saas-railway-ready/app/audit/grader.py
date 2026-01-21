import time
# Ensure these function names match exactly what is exported in the sub-files
from app.audit.crawler import crawl_site
from app.audit.performance import get_performance_metrics
from app.audit.links import check_links

GRADE_BANDS = [(90,'A+'),(80,'A'),(70,'B'),(60,'C'),(0,'D')]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    penalties = 0
    penalties += onpage.get('missing_title_tags', 0) * 2
    penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
    penalties += onpage.get('multiple_h1', 0) * 1
    penalties += links.get('total_broken_links', 0) * 0.5
    
    # Performance score
    lcp = perf.get('lcp_ms', 4000) or 4000
    fcp = perf.get('fcp_ms', 2000) or 2000
    perf_score = max(0, 100 - (lcp/40 + fcp/30))
    
    # Site coverage
    coverage = min(100, crawl_pages_count * 2)
    
    raw = (max(0, 100 - penalties) * 0.5) + (perf_score * 0.3) + (coverage * 0.2)
    overall = max(0, min(100, raw))
    
    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break
            
    return round(overall, 2), grade, {
        'performance': round(perf_score, 2),
        'onpage': max(0, 100 - penalties),
        'coverage': coverage
    }

def run_audit(url: str):
    """
    Main orchestration function.
    """
    # 1. Execute sub-tasks
    crawl_data = crawl_site(url)
    perf_data = get_performance_metrics(url)
    link_data = check_links(url)
    
    # 2. Compute final result
    score, grade, breakdown = compute_scores(
        onpage=crawl_data.get('onpage_stats', {}),
        perf=perf_data,
        links=link_data,
        crawl_pages_count=crawl_data.get('pages_crawled', 0)
    )
    
    return {
        "url": url,
        "overall_score": score,
        "grade": grade,
        "performance": breakdown['performance'],
        "onpage": breakdown['onpage'],
        "coverage": breakdown['coverage'],
        "timestamp": int(time.time()),
        "raw_results": {
            "crawler": crawl_data,
            "performance": perf_data,
            "links": link_data
        }
    }
