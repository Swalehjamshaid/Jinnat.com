
from .crawler import CrawlResult

def analyze_links(crawl: CrawlResult):
    total = len(crawl.broken_internal) + len(crawl.broken_external)
    return {
        'total_broken_links': total,
        'internal_broken_links': len(crawl.broken_internal),
        'external_broken_links': len(crawl.broken_external),
        'status_code_distribution': dict(crawl.status_counts),
    }
