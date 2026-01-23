
import requests
from .logger import log
from ..settings import get_settings

def get_resend_domain_status():
    s = get_settings()
    if not s.RESEND_API_KEY:
        return {'enabled': False, 'reason': 'RESEND_API_KEY missing'}
    try:
        r = requests.get('https://api.resend.com/domains', headers={'Authorization': f'Bearer {s.RESEND_API_KEY}'}, timeout=15)
        r.raise_for_status()
        data = r.json()
        domain = (s.RESEND_DOMAIN or '').strip().lower()
        found = None
        for d in data.get('data', []):
            if d.get('name','').lower() == domain:
                found = d; break
        if not found:
            return {'enabled': True, 'configured': False, 'message': 'Domain not added in Resend', 'domains': data.get('data', [])}
        return {'enabled': True, 'configured': True, 'status': found.get('status'), 'region': found.get('region'), 'name': found.get('name')}
    except Exception as e:
        return {'enabled': False, 'error': str(e)}

def ensure_resend_ready():
    s = get_settings()
    if not s.RESEND_VERIFY_ON_STARTUP:
        return
    st = get_resend_domain_status()
    log('Resend domain check', st)
