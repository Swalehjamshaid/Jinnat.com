import time
from app.audit.crawler import crawl_site, perform_crawl 
from app.audit.performance import get_performance_metrics
from app.audit.links import check_links

GRADE_BANDS = [(90,'A+'),(80,'A'),(70,'B'),(60,'C'),(0,'D')]

def compute_scores(onpage: dict, perf: dict, links: dict, crawl_pages_count: int):
    # Calculate Individual Category Scores
    # 1. SEO Score
    penalties = 0
    penalties += onpage.get('missing_title_tags', 0) * 2
    penalties += onpage.get('missing_meta_descriptions', 0) * 1.5
    seo_score = max(0, 100 - penalties)
    
    # 2. Performance Score
    lcp = perf.get('lcp_ms', 4000) or 4000
    perf_score = max(0, 100 - (lcp/40))
    
    # 3. Connection/Coverage Score
    coverage_score = min(100, crawl_pages_count * 2)
    
    # Overall Calculation
    overall = (seo_score * 0.5) + (perf_score * 0.3) + (coverage_score * 0.2)
    
    grade = 'D'
    for cutoff, letter in GRADE_BANDS:
        if overall >= cutoff:
            grade = letter
            break
            
    # Return both the individual categories and the totals
    categories = {
        "SEO & Content": {"score": round(seo_score, 2), "color": "#4F46E5"},
        "Performance": {"score": round(perf_score, 2), "color": "#10B981"},
        "Site Coverage": {"score": round(coverage_score, 2), "color": "#F59E0B"}
    }
    
    return round(overall, 2), grade, categories

def run_audit(url: str):
    crawl_obj = perform_crawl(str(url)) 
    
    crawl_summary = {
        "pages_crawled": len(crawl_obj.pages),
        "onpage_stats": {
            "missing_title_tags": 0, 
            "missing_meta_descriptions": 0,
            "multiple_h1": 0
        }
    }
    
    link_data = check_links(crawl_obj) 
    perf_data = get_performance_metrics(str(url))
    
    # Get scores and the new categories dictionary
    score, grade, categories = compute_scores(
        crawl_summary['onpage_stats'], 
        perf_data, 
        link_data, 
        crawl_summary['pages_crawled']
    )
    
    return {
        "url": str(url),
        "overall_score": score,
        "grade": grade,
        "timestamp": int(time.time()),
        "categories": categories, # This is what the UI will use
        "performance": perf_data,
        "links": link_data
    }
