import requests
from typing import Optional
from requests.exceptions import RequestException, Timeout
from ..settings import get_settings

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
        'category': ['PERFORMANCE', 'ACCESSIBILITY', 'BEST_PRACTICES', 'SEO'],
        'key': settings.PSI_API_KEY
    }

    try:
        r = requests.get(API, params=params, timeout=50)
        r.raise_for_status()
        data = r.json()

        lh = data.get('lighthouseResult', {})
        audits = lh.get('audits', {})
        categories = lh.get('categories', {})

        loading = data.get('loadingExperience', {}) or data.get('originLoadingExperience', {})
        metrics_field = loading.get('metrics', {}) if isinstance(loading, dict) else {}

        def get_audit_num(key):
            a = audits.get(key, {})
            return a.get('numericValue')

        def get_field_percentile(key):
            m = metrics_field.get(key, {})
            return m.get('percentile')

        def get_category_score(key):
            cat = categories.get(key, {})
            return cat.get('score') * 100 if cat.get('score') is not None else None

        result = {
            'strategy': strategy,
            'lab': {
                'lcp_ms': get_audit_num('largest-contentful-paint'),
                'fcp_ms': get_audit_num('first-contentful-paint'),
                'cls': get_audit_num('cumulative-layout-shift'),
                'tbt_ms': get_audit_num('total-blocking-time'),
                'speed_index_ms': get_audit_num('speed-index'),
                'tti_ms': get_audit_num('interactive'),
            },
            'field': {
                'lcp_ms': get_field_percentile('LARGEST_CONTENTFUL_PAINT_MS'),
                'cls': get_field_percentile('CUMULATIVE_LAYOUT_SHIFT_SCORE'),
                'fid_ms': get_field_percentile('FIRST_INPUT_DELAY_MS'),
                'inp_ms': get_field_percentile('INTERACTION_TO_NEXT_PAINT'),
            },
            'categories': {
                'performance_score': get_category_score('performance'),
                'accessibility_score': get_category_score('accessibility'),
                'best_practices_score': get_category_score('best-practices'),
                'seo_score': get_category_score('seo'),
            },
        }

        return result

    except (Timeout, RequestException):
        return None
    except Exception:
        return None
