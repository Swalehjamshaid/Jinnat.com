import hashlib
from typing import Dict, Any

# Deterministic, offline-friendly scoring based on URL hash.

def _score_from_url(url: str) -> float:
    h = hashlib.sha256(url.encode('utf-8')).digest()
    # produce 0..100
    return round((int.from_bytes(h[:2], 'big') / 65535) * 100, 2)


def _grade(score: float) -> str:
    if score >= 90: return 'A+'
    if score >= 80: return 'A'
    if score >= 70: return 'B'
    if score >= 60: return 'C'
    if score >= 50: return 'D'
    return 'E'


def audit_site_sync(url: str) -> Dict[str, Any]:
    score = _score_from_url(url)
    coverage = round(60 + (score / 100) * 40, 2)
    metrics = {
        'performance': round(score * 0.9, 2),
        'seo': round(score * 0.85, 2),
        'accessibility': round(score * 0.8, 2),
        'best_practices': round(score * 0.75, 2)
    }
    summary = {
        'highlights': [
            'Deterministic offline audit for demo/preview environments',
            'Replace with real crawler/lighthouse in production'
        ],
        'recommendations': [
            'Optimize images and caching',
            'Improve heading hierarchy',
            'Add alt attributes to images'
        ]
    }
    return {
        'overall': {'score': score, 'grade': _grade(score), 'coverage': coverage},
        'metrics': metrics,
        'summary': summary,
    }
