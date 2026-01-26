
"""FFTech Audit Package

Modules:
- runner: main orchestration for a single-page audit with chart-ready data.
- crawler: BFS crawler for same-host pages and link health.
- grader: standalone page grader (SEO/Performance/Security/Content) not used by runner but available.
- seo, links, performance, record, psi: modular analyzers/utilities (optional helpers).
- competitor_report: very small PDF helper (example only).

This package is imported by app.main (FastAPI) via: from app.audit.runner import run_audit
"""
__all__ = ['run_audit']
