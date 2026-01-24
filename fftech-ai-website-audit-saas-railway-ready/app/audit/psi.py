# app/audit/psi.py
import requests
import logging

logger = logging.getLogger(__name__)

def fetch_psi(url: str, strategy: str = 'desktop', api_key: str = None):
    """
    World-Class PSI Fetcher:
    - Requests all 4 major Lighthouse categories.
    - Handles API key security and timeouts.
    """
    # Fallback to settings if key isn't passed directly
    if not api_key:
        from ..settings import get_settings
        api_key = get_settings().PSI_API_KEY
    
    if not api_key:
        logger.error("❌ No API Key found. Audit cannot proceed.")
        return None

    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    
    # NEW: We now request all categories to populate the World-Class Dashboard
    params = {
        'url': url, 
        'key': api_key, 
        'strategy': strategy,
        'category': [
            'PERFORMANCE',
            'SEO',
            'ACCESSIBILITY',
            'BEST_PRACTICES'
        ]
    }

    try:
        # Increase timeout to 60s because requesting 4 categories takes longer
        response = requests.get(endpoint, params=params, timeout=60)
        
        if response.status_code != 200:
            logger.error(f"❌ Google API Error {response.status_code}: {response.text}")
            return None
            
        return response.json()

    except requests.exceptions.Timeout:
        logger.error(f"⏳ PSI Request timed out for {url}")
        return None
    except Exception as e:
        logger.error(f"❌ PSI Request failed: {e}")
        return None
