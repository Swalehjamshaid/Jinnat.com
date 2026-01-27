# app/audit/performance.py
def calculate_performance_score(lcp_ms: int) -> int:
    """
    Calculate page performance score based on LCP (Largest Contentful Paint in ms)
    """
    if lcp_ms < 1000:
        return 100
    elif lcp_ms < 2000:
        return 80
    elif lcp_ms < 3000:
        return 60
    elif lcp_ms < 5000:
        return 40
    else:
        return 20
