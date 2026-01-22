import requests
from typing import Optional
from ..settings import get_settings
from requests.exceptions import RequestException, Timeout

API = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'


def fetch_psi(url: str, strategy: str = 'mobile') -> Optional[dict]:
    """
    Fetches PageSpeed Insights (PSI) data using Google API.
    Returns structured lab + field metrics or None on failure.
    """
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
        r = requests.get(API, params=params, timeout=40)  # Slightly longer timeout for PSI
        r.raise_for_status()

        data = r.json()

        # Extract Lighthouse (lab) results
        lighthouse = data.get('lighthouseResult', {}) or {}
        audits = lighthouse.get('audits', {}) or {}

        # Extract field (CrUX real-user) data
        loading_exp = data.get('loadingExperience', {}) or {}
        origin_loading_exp = data.get('originLoadingExperience', {}) or {}
        field_data = origin_loading_exp if origin_loading_exp.get('metrics') else loading_exp

        metrics_field = field_data.get('metrics', {}) if isinstance(field_data, dict) else {}

        # Helper to safely get numeric audit value (in ms or score)
        def get_audit_num(key: str) -> Optional[float]:
            audit = audits.get(key, {})
            numeric = audit.get('numericValue')
            return numeric if numeric is not None else None

        # Helper for field percentile
        def get_field_percentile(key: str) -> Optional[float]:
            m = metrics_field.get(key, {})
            return m.get('percentile') if isinstance(m, dict) else None

        result = {
            'strategy': strategy,
            'lab': {
                'lcp_ms': get_audit_num('largest-contentful-paint'),
                'fcp_ms': get_audit_num('first-contentful-paint'),
                'cls': get_audit_num('cumulative-layout-shift'),
                'tbt_ms': get_audit_num('total-blocking-time'),
                'speed_index_ms': get_audit_num('speed-index'),
                'tti_ms': get_audit_num('interactive'),           # Time to Interactive
                'si_score': audits.get('speed-index', {}).get('score'),  # 0-1 Lighthouse score
            },
            'field': {
                'lcp_ms': get_field_percentile('LARGEST_CONTENTFUL_PAINT_MS'),
                'cls': get_field_percentile('CUMULATIVE_LAYOUT_SHIFT_SCORE'),
                'fid_ms': get_field_percentile('FIRST_INPUT_DELAY_MS'),
                'inp_ms': get_field_percentile('INTERACTION_TO_NEXT_PAINT'),
            },
            # Optional: quick approximate overall performance score (0-100)
            'approx_performance_score': None
        }

        # Optional: simple combined score approximation (if lab data exists)
        lab = result['lab']
        if lab['lcp_ms'] is not None:
            # Rough approximation based on common PSI scoring logic
            lcp_score = max(0, 100 - (lab['lcp_ms'] - 2500) / 12) if lab['lcp_ms'] > 2500 else 100
            cls_score = max(0, 100 - lab['cls'] * 10000) if lab['cls'] is not None else 100
            combined = (lcp_score * 0.4 + cls_score * 0.3 + (lab['si_score'] or 0) * 100 * 0.3)
            result['approx_performance_score'] = round(combined, 1)

        return result

    except Timeout:
        return None
    except RequestException as e:
        # 4xx, 5xx, connection errors, etc.
        return None
    except Exception:
        # Any other unexpected issue (JSON decode, etc.)
        return None
