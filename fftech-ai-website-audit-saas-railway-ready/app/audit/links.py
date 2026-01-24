# app/audit/links.py

from .crawler import CrawlResult

def analyze_links(crawl: CrawlResult):
    """
    Summarizes link health data from a CrawlResult instance.
    This summary is used by grader.py to calculate score penalties.
    """
    # Safeguard against missing lists
    broken_int = getattr(crawl, 'broken_internal', [])
    broken_ext = getattr(crawl, 'broken_external', [])
    
    total = len(broken_int) + len(broken_ext)
    
    return {
        'total_broken_links': total,
        'internal_broken_links': len(broken_int),
        'external_broken_links': len(broken_ext),
        # distribution of HTTP status codes (200, 404, 500, etc.)
        'status_code_distribution': dict(getattr(crawl, 'status_counts', {})),
    }
