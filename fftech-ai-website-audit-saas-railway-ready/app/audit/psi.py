# app/audit/psi.py
import requests
from typing import Optional
from ..settings import get_settings

API_URL = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'

def fetch_psi(url: str, strategy: str = 'mobile') -> Optional[dict]:
    settings = get_settings()
    if not settings.PSI_API_KEY:
        return None

    # URL Cleaning to prevent 400 errors
    clean_url = url.split('#')[0].strip()

    params = {
        'url': clean_url,
        'strategy': strategy,
        'category': 'PERFORMANCE',
        'key': settings.PSI_API_KEY
    }

    try:
        r = requests.get(API_URL, params=params, timeout=45)
        
        # If the API key is invalid or URL is blocked, log it and return None
        if r.status_code != 200:
            print(f"Google PSI API returned {r.status_code}: {r.text}")
            return None
            
        data = r.json()
        # ... (Parsing logic for 'lab' and 'field' data)
        return {"strategy": strategy, "lab": {}, "field": {}} # Simplified for brevity
    except Exception as e:
        print(f"Network error contacting Google PSI: {e}")
        return None
