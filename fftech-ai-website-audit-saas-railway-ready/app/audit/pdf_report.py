# -*- coding: utf-8 -*-
"""
app/audit/pdf_service.py

Adapter (Best Practice):
- Accepts runner.py result dict (audited_url, overall_score, grade, breakdown, chart_data, dynamic)
- Converts it into audit_data required by pdf_report.generate_audit_pdf
- Generates PDF

This keeps runner.py I/O unchanged and makes PDF generation stable.
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


def _as_list(x) -> List[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _derive_risks_and_opps(runner_result: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Derive human-readable risks/opportunities from runner output (no runner changes needed)."""
    risks: List[str] = []
    opps: List[str] = []

    breakdown = runner_result.get("breakdown") or {}
    seo_extras = _safe_get(breakdown, "seo", "extras", default={}) or {}
    perf_extras = _safe_get(breakdown, "performance", "extras", default={}) or {}
    sec = breakdown.get("security") or {}
    links = breakdown.get("links") or {}

    # SEO
    if not seo_extras.get("title"):
        risks.append("Missing <title> tag may reduce search visibility.")
        opps.append("Add a clear, keyword-focused title tag (50–60 chars).")

    if seo_extras.get("meta_description_present") is False:
        risks.append("Missing meta description can reduce click-through rate from Google.")
        opps.append("Write compelling meta descriptions to improve CTR.")

    h1 = seo_extras.get("h1_count")
    if isinstance(h1, int) and h1 == 0:
        risks.append("No H1 found; page topic may be unclear to users/search engines.")
        opps.append("Add a single strong H1 that matches page intent.")
    elif isinstance(h1, int) and h1 > 1:
        risks.append("Multiple H1s found; heading structure may be unclear.")
        opps.append("Use one H1 per page and use H2/H3 for sections.")

    imgs_total = seo_extras.get("images_total")
    missing_alt = seo_extras.get("images_missing_alt")
    if isinstance(imgs_total, int) and isinstance(missing_alt, int) and imgs_total >= 5 and missing_alt > 0:
        risks.append("Images missing ALT attributes reduce accessibility and SEO value.")
        opps.append("Add descriptive ALT text to key images.")

    if not seo_extras.get("canonical"):
        risks.append("Canonical link not detected; risk of duplicate content signals.")
        opps.append("Add rel=canonical on important pages.")

    # Performance
    load_ms = perf_extras.get("load_ms")
    size_bytes = perf_extras.get("bytes")
    if isinstance(load_ms, int) and load_ms > 3000:
        risks.append(f"Slow load time detected ({load_ms} ms) can reduce conversions.")
        opps.append("Optimize images, reduce JS/CSS, enable caching/CDN.")

    if isinstance(size_bytes, int) and size_bytes > 1_500_000:
        risks.append("Large page size can hurt mobile performance.")
        opps.append("Compress images, minify assets, use WebP/AVIF.")

    # Security
    if sec.get("https") is False:
        risks.append("HTTPS is disabled; users may see security warnings.")
        opps.append("Enable SSL/TLS to improve trust and SEO.")
    elif sec.get("https") is True and sec.get("hsts") is False:
        risks.append("HSTS header missing; HTTPS enforcement can be improved.")
        opps.append("Enable HSTS for stronger security.")

    # Links
    if (links.get("internal_links_count") or 0) == 0:
        risks.append("No internal links detected; poor crawl/navigation structure.")
        opps.append("Add internal links to key pages (services, product, contact).")

    # Limit to keep PDF clean
    return risks[:10], opps[:10]


def map_runner_result_to_audit_data(
    runner_result: Dict[str, Any],
    client_name: str = "N/A",
    brand_name: str = "FF Tech",
    audit_date: Optional[str] = None,
    website_name: Optional[str] = None,
    industry: str = "N/A",
    audience: str = "N/A",
    goals: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convert runner output into audit_data structure expected by pdf_report.py."""
    audit_date = audit_date or _today_iso()
    goals = goals or []

    audited_url = runner_result.get("audited_url") or "N/A"
    overall_score = runner_result.get("overall_score")
    grade = runner_result.get("grade") or "N/A"

    breakdown = runner_result.get("breakdown") or {}
    seo_extras = _safe_get(breakdown, "seo", "extras", default={}) or {}
    perf_extras = _safe_get(breakdown, "performance", "extras", default={}) or {}

    risks, opps = _derive_risks_and_opps(runner_result)

    # Build scores
    scores = {
        "seo": _safe_get(breakdown, "seo", "score", default=None),
        "performance": _safe_get(breakdown, "performance", "score", default=None),
        "ux_ui": None,
        "accessibility": None,
        "security": _safe_get(breakdown, "security", "score", default=None),
        "content_quality": None,
    }

    # Derive simple lists
    on_page_issues = []
    if not seo_extras.get("title"):
        on_page_issues.append("Missing <title> tag.")
    if seo_extras.get("meta_description_present") is False:
        on_page_issues.append("Missing meta description.")
    if seo_extras.get("h1_count") == 0:
        on_page_issues.append("No H1 heading found.")
    if isinstance(seo_extras.get("images_missing_alt"), int) and seo_extras.get("images_missing_alt", 0) > 0:
        on_page_issues.append("Some images missing ALT attributes.")

    technical_issues = []
    if not seo_extras.get("canonical"):
        technical_issues.append("Canonical link not detected.")

    perf_issues = []
    if isinstance(perf_extras.get("load_ms"), int) and perf_extras["load_ms"] > 3000:
        perf_issues.append(f"Slow load time: {perf_extras['load_ms']} ms.")
    if isinstance(perf_extras.get("bytes"), int) and perf_extras["bytes"] > 1_500_000:
        perf_issues.append(f"Large page size: {perf_extras['bytes']} bytes.")
    if isinstance(perf_extras.get("scripts"), int) and perf_extras["scripts"] > 25:
        perf_issues.append("High number of scripts may impact performance.")
    if isinstance(perf_extras.get("styles"), int) and perf_extras["styles"] > 12:
        perf_issues.append("High number of stylesheets may impact rendering performance.")

    verdict = "Healthy" if isinstance(overall_score, int) and overall_score >= 80 else "Needs Improvement"

    audit_data: Dict[str, Any] = {
        "website": {
            "name": website_name or audited_url,
            "url": audited_url,
            "industry": industry,
            "audience": audience,
            "goals": goals,
        },
        "client": {"name": client_name},
        "brand": {"name": brand_name},
        "audit": {
            "date": audit_date,
            "overall_score": overall_score,
            "grade": grade,
            "verdict": verdict,
            "executive_summary": (
                "This report summarizes the website’s current health based on automated checks across "
                "SEO, performance, links, and security."
            ),
            "key_risks": risks,
            "opportunities": opps,
        },
        "scope": {
            "what": [
                "SEO signals (title, meta description, canonical, headings, image ALT)",
                "Performance heuristics (load time, bytes, scripts, styles)",
                "Links (internal/external counts)",
                "Security basics (HTTPS, HSTS, HTTP status)",
            ],
            "why": "These elements influence visibility, usability, trust, and conversion performance.",
            "tools": ["FFTechAuditBot runner.py", "ReportLab PDF generator"],
        },
        "scores": scores,
        "seo": {
            "on_page_issues": on_page_issues,
            "technical_issues": technical_issues,
            "content_gaps": [],
            "keyword_optimization_level": "N/A",
        },
        "performance": {
            "core_web_vitals": {
                "lcp": "N/A",
                "cls": "N/A",
                "inp": "N/A",
                "lcp_notes": "",
                "cls_notes": "",
                "inp_notes": "",
            },
            "mobile_vs_desktop": "N/A",
            "page_size_issues": perf_issues,
        },
        "mobile": {
            "responsive_issues": [],
            "mobile_usability_problems": [],
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
    Single entry point for PDF generation:
    runner_result -> mapped audit_data -> generate_audit_pdf
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
