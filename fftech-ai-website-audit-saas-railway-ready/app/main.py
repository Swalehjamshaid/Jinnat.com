# -*- coding: utf-8 -*-
"""
app/audit/pdf_service.py

Adapter layer (best practice):
- Accepts runner.py output (stable)
- Maps it into pdf_report.py audit_data format
- Calls generate_audit_pdf()

This keeps runner.py input/output unchanged.
"""

from __future__ import annotations

import os
import datetime as dt
from typing import Any, Dict, Optional, List, Tuple

from app.audit.pdf_report import generate_audit_pdf


def _safe_get(d: Dict[str, Any], *path: str, default=None):
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _today_iso() -> str:
    return dt.date.today().isoformat()


def _derive_risks_opps(result: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Derive basic risks/opportunities from runner output (optional, but makes PDF smarter)."""
    risks: List[str] = []
    opps: List[str] = []

    b = result.get("breakdown") or {}

    seo_extras = _safe_get(b, "seo", "extras", default={}) or {}
    perf_extras = _safe_get(b, "performance", "extras", default={}) or {}
    sec = _safe_get(b, "security", default={}) or {}
    links = _safe_get(b, "links", default={}) or {}

    if seo_extras.get("meta_description_present") is False:
        risks.append("Missing meta description can reduce click-through rate from Google results.")
        opps.append("Write compelling meta descriptions for key pages to improve CTR.")

    h1_count = seo_extras.get("h1_count")
    if isinstance(h1_count, int) and h1_count == 0:
        risks.append("No H1 detected; page topic clarity may be reduced.")
        opps.append("Add exactly one H1 aligned with the primary topic/keyword.")
    elif isinstance(h1_count, int) and h1_count > 1:
        risks.append("Multiple H1 tags detected; heading hierarchy may be unclear.")
        opps.append("Use one H1 and structure content with H2/H3 headings.")

    imgs_total = seo_extras.get("images_total")
    imgs_missing_alt = seo_extras.get("images_missing_alt")
    if isinstance(imgs_total, int) and isinstance(imgs_missing_alt, int) and imgs_total >= 5 and imgs_missing_alt > 0:
        risks.append("Some images lack ALT text, impacting accessibility and SEO.")
        opps.append("Add descriptive ALT text to images, especially important content images.")

    load_ms = perf_extras.get("load_ms")
    if isinstance(load_ms, int) and load_ms > 3000:
        risks.append(f"Slow load time detected ({load_ms} ms) which may reduce conversions.")
        opps.append("Optimize images, minify assets, and reduce render-blocking scripts.")

    bytes_ = perf_extras.get("bytes")
    if isinstance(bytes_, int) and bytes_ > 1_500_000:
        risks.append("Large page size can slow down mobile experience.")
        opps.append("Compress images and use WebP/AVIF; defer non-critical resources.")

    if sec.get("https") is False:
        risks.append("HTTPS is not enabled, which reduces trust and security.")
        opps.append("Enable SSL/TLS (HTTPS) and enforce redirects from HTTP to HTTPS.")

    if sec.get("https") is True and sec.get("hsts") is False:
        risks.append("HSTS header missing; HTTPS enforcement can be improved.")
        opps.append("Enable HSTS to strengthen transport security.")

    if (links.get("internal_links_count") or 0) == 0:
        risks.append("No internal links detected; crawlability and navigation may be weak.")
        opps.append("Add internal links to key pages to improve structure and SEO.")

    return risks[:8], opps[:8]


def map_runner_result_to_audit_data(
    runner_result: Dict[str, Any],
    client_name: str = "N/A",
    brand_name: str = "FF Tech",
    audit_date: Optional[str] = None,
    website_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Map runner output -> pdf_report audit_data structure.
    """
    audit_date = audit_date or _today_iso()

    audited_url = runner_result.get("audited_url") or "N/A"
    overall_score = runner_result.get("overall_score")
    grade = runner_result.get("grade") or "N/A"

    breakdown = runner_result.get("breakdown") or {}

    scores = {
        "seo": _safe_get(breakdown, "seo", "score", default=None),
        "performance": _safe_get(breakdown, "performance", "score", default=None),
        "ux_ui": None,
        "accessibility": None,
        "security": _safe_get(breakdown, "security", "score", default=None),
        "content_quality": None,
    }

    risks, opps = _derive_risks_opps(runner_result)

    audit_data: Dict[str, Any] = {
        "website": {
            "name": website_name or audited_url,
            "url": audited_url,
            "industry": "N/A",
            "audience": "N/A",
            "goals": [],
        },
        "client": {"name": client_name},
        "brand": {"name": brand_name},
        "audit": {
            "date": audit_date,
            "overall_score": overall_score,
            "grade": grade,
            "verdict": "Healthy" if isinstance(overall_score, int) and overall_score >= 80 else "Needs Improvement",
            "executive_summary": "This report summarizes the website’s current health based on automated checks.",
            "key_risks": risks,
            "opportunities": opps,
        },
        "scores": scores,

        # Optional sections (you can expand later)
        "scope": {
            "what": ["SEO basics", "Performance heuristics", "Links structure", "Security checks"],
            "why": "These factors impact rankings, UX, trust, and conversions.",
            "tools": ["FF Tech runner.py", "ReportLab PDF generator"],
        },
        "seo": {
            "on_page_issues": [],
            "technical_issues": [],
            "content_gaps": [],
            "keyword_optimization_level": "N/A",
        },
        "performance": {
            "core_web_vitals": {},
            "mobile_vs_desktop": "N/A",
            "page_size_issues": [],
        },
        "mobile": {
            "responsive_issues": [],
            "usability_problems": [],
            "mobile_score": None,
        },
    }

    return audit_data


def generate_pdf_from_runner_result(
    runner_result: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    client_name: str = "N/A",
    brand_name: str = "FF Tech",
    audit_date: Optional[str] = None,
    website_name: Optional[str] = None,
) -> str:
    """
    One-call function:
    runner_result -> audit_data -> generate_audit_pdf
    """
    audit_data = map_runner_result_to_audit_data(
        runner_result=runner_result,
        client_name=client_name,
        brand_name=brand_name,
        audit_date=audit_date,
        website_name=website_name,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    return generate_audit_pdf(
        audit_data=audit_data,
        output_path=output_path,
        logo_path=logo_path,
        report_title="Website Audit Report",
    )
