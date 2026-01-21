
import requests
from typing import Optional
from ..settings import get_settings

API = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'

def fetch_psi(url: str, strategy: str = 'mobile') -> Optional[dict]:
    settings = get_settings()
    if not settings.PSI_API_KEY:
        return None
    params = {
        'url': url,
        'strategy': strategy,
        'category': 'PERFORMANCE',
        'key': settings.PSI_API_KEY
    }
    try:
        r = requests.get(API, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        lh = data.get('lighthouseResult', {}) or {}
        audits = lh.get('audits', {}) or {}
        loading = data.get('loadingExperience', {}) or data.get('originLoadingExperience', {}) or {}
        metrics = loading.get('metrics', {}) if isinstance(loading, dict) else {}
        def audit_num(key):
            a = audits.get(key, {})
            return a.get('numericValue')
        def metric_percentile(key):
            m = metrics.get(key, {})
            return m.get('percentile')
        return {
            'strategy': strategy,
            'lab': {
                'lcp_ms': audit_num('largest-contentful-paint'),
                'fcp_ms': audit_num('first-contentful-paint'),
                'cls': audit_num('cumulative-layout-shift'),
                'tbt_ms': audit_num('total-blocking-time'),
                'speed_index_ms': audit_num('speed-index'),
                'tti_ms': audit_num('interactive'),
            },
            'field': {
                'lcp_ms': metric_percentile('LARGEST_CONTENTFUL_PAINT_MS'),
                'cls': metric_percentile('CUMULATIVE_LAYOUT_SHIFT_SCORE'),
                'fid_ms': metric_percentile('FIRST_INPUT_DELAY_MS'),
                'inp_ms': metric_percentile('INTERACTION_TO_NEXT_PAINT'),
            }
        }
    except Exception:
        return None
