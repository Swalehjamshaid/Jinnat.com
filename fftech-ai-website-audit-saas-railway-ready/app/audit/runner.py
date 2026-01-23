from urllib.parse import urlparse

# CRITICAL: No self-import here.

def _normalize_url(url):
    """
    Fixes AttributeError: 'HttpUrl' object has no attribute 'decode'
    by casting to string before parsing.
    """
    url_str = str(url)
    parsed = urlparse(url_str)
    return parsed.geturl()

async def run_audit(url):
    """
    Core auditing logic.
    """
    target = _normalize_url(url)
    # Perform your audit here...
    return {"status": "success", "url": target, "score": 100}
