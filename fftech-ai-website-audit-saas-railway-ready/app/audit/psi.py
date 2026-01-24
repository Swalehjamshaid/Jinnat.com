# app/audit/psi.py
import requests
import logging

logger = logging.getLogger(__name__)

def fetch_psi(url: str, strategy: str = 'mobile'):
    settings = get_settings()
    # Ensure this variable in Railway is the AIza... string
    api_key = settings.PSI_API_KEY 
    
    if not api_key:
        return None

    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {'url': url, 'key': api_key, 'strategy': strategy}

    try:
        # CRITICAL FIX: Timeout set to 15s so the app doesn't hang forever
        response = requests.get(endpoint, params=params, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"Google PSI Error: {response.text}")
            return None
            
        return response.json()
    except requests.exceptions.Timeout:
        logger.warning(f"Google PSI timed out for {url}. Switching to fallback.")
        return None
    except Exception as e:
        logger.error(f"PSI Module Error: {e}")
        return None
