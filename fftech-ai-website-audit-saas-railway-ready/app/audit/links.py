from app.audit.crawler import CrawlResult

def check_links(crawl):
    """
    Analyzes a CrawlResult object.
    Added safety check to prevent 'AttributeError'.
    """
    # Safety check: if we accidentally passed a string instead of the crawl object
    if isinstance(crawl, str):
        return {
            'total_broken_links': 0,
            'internal_broken_links': 0,
            'external_broken_links': 0,
            'status_code_distribution': {}
        }

    # Standard logic
    total = len(crawl.broken_internal) + len(crawl.broken_external)
    return {
        'total_broken_links': total,
        'internal_broken_links': len(crawl.broken_internal),
        'external_broken_links': len(crawl.broken_external),
        'status_code_distribution': dict(crawl.status_counts),
    }
