from typing import Dict
from .crawler import CrawlResult

def analyze_links(crawl: CrawlResult) -> Dict[str, float]:
    """
    Summarizes link health data from a CrawlResult instance.
    Provides metrics for grader.py to calculate score penalties.
    Fully Python-based.
    """
    broken_int = getattr(crawl, 'broken_internal', [])
    broken_ext = getattr(crawl, 'broken_external', [])
    internal_links = getattr(crawl, 'internal_links', {})
    external_links = getattr(crawl, 'external_links', {})
    status_counts = getattr(crawl, 'status_counts', {})

    total_broken = len(broken_int) + len(broken_ext)
    total_internal_links = sum(len(v) for v in internal_links.values())
    total_external_links = sum(len(v) for v in external_links.values())
    total_links = total_internal_links + total_external_links

    internal_ratio = (total_internal_links / total_links * 100) if total_links else 0
    external_ratio = (total_external_links / total_links * 100) if total_links else 0
    broken_ratio = (total_broken / total_links * 100) if total_links else 0

    summary = {
        "total_broken_links": total_broken,
        "internal_broken_links": len(broken_int),
        "external_broken_links": len(broken_ext),
        "total_internal_links": total_internal_links,
        "total_external_links": total_external_links,
        "internal_link_ratio": round(internal_ratio, 1),
        "external_link_ratio": round(external_ratio, 1),
        "broken_link_ratio": round(broken_ratio, 1),
        "status_code_distribution": dict(status_counts),
    }

    return summary
