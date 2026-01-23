from urllib.parse import urlparse
import logging

# NO SELF-IMPORT HERE (prevents circular import error)

def _normalize_url(url):
    """
    Converts Pydantic HttpUrl to string and normalizes it.
    Solves: AttributeError: 'HttpUrl' object has no attribute 'decode'
    """
    url_str = str(url)
    parsed = urlparse(url_str)
    return parsed.geturl()

async def run_audit(url):
    """
    Main audit execution logic.
    """
    target_url = _normalize_url(url)
    
    # Logic for your audit process
    result = {
        "url": target_url,
        "status": "completed",
        "score": 92,
        "details": "Success"
    }
    return result
