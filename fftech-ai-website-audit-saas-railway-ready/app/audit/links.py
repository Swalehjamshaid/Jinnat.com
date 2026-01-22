from app.audit.crawler import CrawlResult
from collections import Counter


def check_links(crawl):
    """
    Analyzes link health from a CrawlResult object.
    Returns consistent structure even if input is invalid or incomplete.
    """
    default_result = {
        'total_broken_links': 0,
        'internal_broken_links': 0,
        'external_broken_links': 0,
        'status_code_distribution': {}
    }

    if not isinstance(crawl, CrawlResult):
        return default_result

    broken_internal = getattr(crawl, 'broken_internal', [])
    redirects = getattr(crawl, 'redirects', [])

    internal_broken_count = len(broken_internal)
    external_broken_count = 0  # If you add external check later

    total_broken = internal_broken_count + external_broken_count

    status_distribution = dict(getattr(crawl, 'status_counts', {}))

    # Detect long redirect chains
    long_chains = len([r for r in redirects if len(r) > 3])  # chains longer than 3

    # Examples
    examples = {}
    if internal_broken_count > 0 and internal_broken_count <= 10:
        examples['broken_internal_examples'] = [item.get('url', 'unknown') for item in broken_internal[:5]]

    return {
        'total_broken_links': total_broken,
        'internal_broken_links': internal_broken_count,
        'external_broken_links': external_broken_count,
        'status_code_distribution': status_distribution,
        'redirect_chains': long_chains,
        **examples
    }
