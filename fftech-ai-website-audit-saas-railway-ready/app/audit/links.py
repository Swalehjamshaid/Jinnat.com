from app.audit.crawler import CrawlResult
from collections import Counter


def check_links(crawl):
    """
    Analyzes link health from a CrawlResult object.
    Returns consistent structure even if input is invalid or incomplete.
    """
    # Default / fallback result when something goes wrong
    default_result = {
        'total_broken_links': 0,
        'internal_broken_links': 0,
        'external_broken_links': 0,
        'status_code_distribution': {}
    }

    # Safety checks for invalid input types
    if crawl is None:
        return default_result

    if not isinstance(crawl, CrawlResult):
        # Could be string URL, dict, or wrong object from previous bug
        return default_result

    # Safe attribute access with defaults
    broken_internal = getattr(crawl, 'broken_internal', [])
    broken_external = getattr(crawl, 'broken_external', [])   # assuming you may add this later
    status_counts = getattr(crawl, 'status_counts', {})

    # Convert broken lists to safe form (handle both list of str and list of dict)
    internal_broken_urls = []
    if broken_internal:
        if isinstance(broken_internal[0], dict):
            internal_broken_urls = [item.get('url', 'unknown') for item in broken_internal]
        else:
            internal_broken_urls = [str(item) for item in broken_internal]

    # Counts
    internal_broken_count = len(internal_broken_urls)
    external_broken_count = len(broken_external) if broken_external else 0
    total_broken = internal_broken_count + external_broken_count

    # Status distribution (always dict of int → int)
    status_distribution = dict(status_counts) if isinstance(status_counts, (dict, Counter)) else {}

    # Optional: add a few example broken URLs if not too many (useful for debugging/reports)
    examples = {}
    if internal_broken_count > 0 and internal_broken_count <= 5:
        examples['broken_internal_examples'] = internal_broken_urls[:3]

    return {
        'total_broken_links': total_broken,
        'internal_broken_links': internal_broken_count,
        'external_broken_links': external_broken_count,
        'status_code_distribution': status_distribution,
        # Optional fields (won't break existing consumers)
        **examples
    }
