import time
from app.audit.crawler import crawl_site, perform_crawl # Import perform_crawl to get the object
from app.audit.performance import get_performance_metrics
from app.audit.links import check_links

GRADE_BANDS = [(90,'A+'),(80,'A'),(70,'B'),(60,'C'),(0,'D')]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    penalties = 0
    penalties += onpage.get('missing_title_tags', 0) * 2
    penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
    
    lcp = perf.get('lcp_ms', 4000) or 4000
    perf_score = max(0, 100 - (lcp/40))
    coverage = min(100, crawl_pages_count * 2)
    
    overall = (max(0, 100 - penalties) * 0.5) + (perf_score * 0.3) + (coverage * 0.2)
    
    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break
    return round(overall, 2), grade

def run_audit(url: str):
    # 1. Run the actual crawl to get the CrawlResult object
    # We use perform_crawl to get the object that links.py needs
    crawl_obj = perform_crawl(str(url)) 
    
    # 2. Get the dictionary version for the scores
    # This is what we previously built to summarize the crawl
    crawl_summary = {
        "pages_crawled": len(crawl_obj.pages),
        "onpage_stats": {
            "missing_title_tags": 0, # Add your logic here or use crawl_site
            "missing_meta_descriptions": 0,
            "multiple_h1": 0
        }
    }
    
    # 3. FIX: Pass the crawl_obj, NOT the url string
    link_data = check_links(crawl_obj) 
    
    # 4. Get Performance
    perf_data = get_performance_metrics(str(url))
    
    # 5. Compute scores
    score, grade = compute_scores(crawl_summary['onpage_stats'], perf_data, link_data, crawl_summary['pages_crawled'])
    
    return {
        "url": str(url),
        "overall_score": score,
        "grade": grade,
        "timestamp": int(time.time()),
        "performance": perf_data,
        "links": link_data
    }
