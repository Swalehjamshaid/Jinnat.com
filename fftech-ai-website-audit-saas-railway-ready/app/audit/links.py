# Updated to absolute import for Docker stability
from app.audit.crawler import CrawlResult

def check_links(crawl: CrawlResult):
    """
    Main entry point for grader.py.
    Renamed from analyze_links to check_links to match grader.py expectations.
    """
    total = len(crawl.broken_internal) + len(crawl.broken_external)
    
    return {
        'total_broken_links': total,
        'internal_broken_links': len(crawl.broken_internal),
        'external_broken_links': len(crawl.broken_external),
        'status_code_distribution': dict(crawl.status_counts),
    }
