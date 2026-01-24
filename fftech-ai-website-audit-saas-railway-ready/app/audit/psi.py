# app/audit/psi.py
import requests
import logging
from ..settings import get_settings

logger = logging.getLogger(__name__)

def fetch_psi(url: str, strategy: str = 'mobile'):
    settings = get_settings()
    
    # We use the AIza... string here, NOT the JSON file
    api_key = settings.PSI_API_KEY 
    
    if not api_key:
        logger.error("PSI_API_KEY is not set in environment variables.")
        return None

    # Google PageSpeed Insights V5 endpoint
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    
    params = {
        'url': url,
        'key': api_key,
        'strategy': strategy,
        'category': ['PERFORMANCE', 'SEO', 'ACCESSIBILITY']
    }

    try:
        response = requests.get(endpoint, params=params, timeout=60)
        
        # This catches the "API key not valid" error specifically
        if response.status_code == 400:
            error_data = response.json()
            logger.error(f"Google API rejected the key: {error_data.get('error', {}).get('message')}")
            return None
            
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        logger.error(f"Failed to fetch PSI data: {e}")
        return None
