# app/audit/psi.py

import requests
from typing import Optional
from ..settings import get_settings

API = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'

def fetch_psi(url: str, strategy: str = 'mobile') -> Optional[dict]:
    """
    Fetches performance metrics from Google PageSpeed Insights API.
    Distinguishes between Lab (Lighthouse) and Field (CrUX) data.
    """
    settings = get_settings()
    
    # Critical Check: If no key is set, return None to trigger performance.py fallback
    if not settings.PSI_API_KEY:
        return None

    params = {
        'url': url,
        'strategy': strategy,
        'category': 'PERFORMANCE',
        'key': settings.PSI_API_KEY
    }

    try:
        # 30-second timeout as PSI can be slow to analyze heavy sites
        r = requests.get(API, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        # 1. Extract Lab Data (Lighthouse Result)
        lh = data.get('lighthouseResult', {}) or {}
        audits = lh.get('audits', {}) or {}

        # 2. Extract Field Data (Real User Experience / CrUX)
        # Check both specific and origin-level loading experiences
        loading = data.get('loadingExperience', {}) or data.get('originLoadingExperience', {}) or {}
        metrics = loading.get('metrics', {}) if isinstance(loading, dict) else {}

        # Helper: Extract numeric audit values
        def audit_num(key):
            a = audits.get(key, {})
            return a.get('numericValue')

        # Helper: Extract percentile values from field metrics
        def metric_percentile(key):
            # Ensure we are checking a dictionary
            m = metrics.get(key, {}) if isinstance(metrics, dict) else {}
            return m.get('percentile') if isinstance(m, dict) else None

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
    except Exception as e:
        # Logs the error but returns None so the app can use fallback performance checks
        print(f"PSI API Error for {url}: {e}")
        return None
