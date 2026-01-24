# app/audit/psi.py
import requests
import logging

logger = logging.getLogger(__name__)

# FIX: Add api_key=None to the arguments list here
def fetch_psi(url: str, strategy: str = 'mobile', api_key: str = None):
    # If no key is passed, try to get it from settings as a fallback
    if not api_key:
        from ..settings import get_settings
        api_key = get_settings().PSI_API_KEY
    
    if not api_key:
        logger.error("No API Key provided for PageSpeed Insights")
        return None

    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        'url': url, 
        'key': api_key, 
        'strategy': strategy,
        'category': 'PERFORMANCE'
    }

    try:
        response = requests.get(endpoint, params=params, timeout=30)
        if response.status_code != 200:
            logger.error(f"Google API Error: {response.text}")
            return None
        return response.json()
    except Exception as e:
        logger.error(f"PSI Request failed: {e}")
        return None
