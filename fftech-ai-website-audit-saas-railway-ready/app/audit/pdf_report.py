# -*- coding: utf-8 -*-
"""
app/audit/pdf_report.py

PDF Generator:
- Pure PDF generation ONLY (no imports from pdf_service/runner to avoid circular imports)
- Exposes: generate_audit_pdf(audit_data, output_path, logo_path, report_title)

This module must NOT import itself.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    try:
        return str(x)
    except Exception:
        return ""


def _draw_heading(c: canvas.Canvas, text: str, x: float, y: float) -> float:
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(colors.black)
    c.drawString(x, y, text)
    return y - 18


def _draw_subheading(c: canvas.Canvas, text: str, x: float, y: float) -> float:
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.black)
    c.drawString(x, y, text)
    return y - 14


def _draw_paragraph(c: canvas.Canvas, text: str, x: float, y: float, max_width: int = 95) -> float:
    """
    Very lightweight line-wrapping (no platypus) to keep dependencies minimal.
    """
    c.setFont("Helvetica", 10.5)
    c.setFillColor(colors.black)

    words = _safe_str(text).split()
    line = ""
    lines: List[str] = []

    for w in words:
        if len(line) + len(w) + 1 <= max_width:
            line = (line + " " + w).strip()
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)

    for ln in lines:
        c.drawString(x, y, ln)
        y -= 12

    return y


def _draw_bullets(c: canvas.Canvas, items: List[str], x: float, y: float, max_items: int = 12) -> float:
    c.setFont("Helvetica", 10.5)
    c.setFillColor(colors.black)

    for i, item in enumerate(items[:max_items]):
        c.drawString(x, y, u"\u2022 " + _safe_str(item))
        y -= 12

    return y


def _new_page_if_needed(c: canvas.Canvas, y: float, min_y: float = 72) -> float:
    if y < min_y:
        c.showPage()
        return A4[1] - 72
    return y


def generate_audit_pdf(
    audit_data: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    report_title: str = "Website Audit Report",
) -> str:
    """
    Generate a PDF at output_path using audit_data.
    Returns output_path.
    """

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    c = canvas.Canvas(output_path, pagesize=A4)
    page_w, page_h = A4

    x = 48
    y = page_h - 60

    # Optional logo
    if logo_path and os.path.exists(logo_path):
        try:
            # Draw logo at top-right
            c.drawImage(logo_path, page_w - 160, page_h - 95, width=110, height=50, preserveAspectRatio=True, mask="auto")
        except Exception:
            # Ignore logo errors, keep generating
            pass

    # Title
    y = _draw_heading(c, report_title, x, y)
    y -= 6

    website = audit_data.get("website") or {}
    client = audit_data.get("client") or {}
    brand = audit_data.get("brand") or {}
    audit = audit_data.get("audit") or {}
    scope = audit_data.get("scope") or {}
    scores = audit_data.get("scores") or {}
    seo = audit_data.get("seo") or {}
    perf = audit_data.get("performance") or {}
    mobile = audit_data.get("mobile") or {}

    # Summary block
    c.setFont("Helvetica", 10.5)
    c.setFillColor(colors.black)

    y = _draw_paragraph(
        c,
        f"Client: {_safe_str(client.get('name', 'N/A'))} | Brand: {_safe_str(brand.get('name', 'N/A'))}",
        x, y
    )
    y = _draw_paragraph(
        c,
        f"Website: {_safe_str(website.get('name', 'N/A'))}  ({_safe_str(website.get('url', 'N/A'))})",
        x, y
    )
    y = _draw_paragraph(
        c,
        f"Audit Date: {_safe_str(audit.get('date', 'N/A'))}",
        x, y
    )

    y -= 6
    y = _new_page_if_needed(c, y)

    # Executive Summary
    y = _draw_subheading(c, "Executive Summary", x, y)
    y = _draw_paragraph(c, _safe_str(audit.get("executive_summary", "")), x, y)
    y -= 6
    y = _new_page_if_needed(c, y)

    # Overall score line
    overall_score = audit.get("overall_score")
    grade = audit.get("grade", "N/A")
    verdict = audit.get("verdict", "N/A")

    y = _draw_subheading(c, "Overall Result", x, y)
    y = _draw_paragraph(
        c,
        f"Overall Score: {_safe_str(overall_score)} | Grade: {_safe_str(grade)} | Verdict: {_safe_str(verdict)}",
        x, y
    )
    y -= 6
    y = _new_page_if_needed(c, y)

    # Scores
    y = _draw_subheading(c, "Section Scores", x, y)
    score_lines = [
        f"SEO: {_safe_str(scores.get('seo'))}",
        f"Performance: {_safe_str(scores.get('performance'))}",
        f"Security: {_safe_str(scores.get('security'))}",
        f"Accessibility: {_safe_str(scores.get('accessibility'))}",
        f"Content Quality: {_safe_str(scores.get('content_quality'))}",
        f"UX/UI: {_safe_str(scores.get('ux_ui'))}",
    ]
    y = _draw_bullets(c, score_lines, x, y, max_items=12)
    y -= 6
    y = _new_page_if_needed(c, y)

    # Key risks & opportunities
    risks = audit.get("key_risks") or []
    opps = audit.get("opportunities") or []

    y = _draw_subheading(c, "Key Risks", x, y)
    y = _draw_bullets(c, [ _safe_str(r) for r in risks ], x, y, max_items=10)
    y -= 4
    y = _new_page_if_needed(c, y)

    y = _draw_subheading(c, "Opportunities", x, y)
    y = _draw_bullets(c, [ _safe_str(o) for o in opps ], x, y, max_items=10)
    y -= 6
    y = _new_page_if_needed(c, y)

    # Scope
    y = _draw_subheading(c, "Audit Scope", x, y)
    y = _draw_paragraph(c, "What we checked:", x, y)
    y = _draw_bullets(c, [ _safe_str(w) for w in (scope.get("what") or []) ], x + 12, y, max_items=12)
    y = _draw_paragraph(c, f"Why it matters: {_safe_str(scope.get('why', ''))}", x, y)
    tools = scope.get("tools") or []
    if tools:
        y = _draw_paragraph(c, "Tools:", x, y)
        y = _draw_bullets(c, [ _safe_str(t) for t in tools ], x + 12, y, max_items=10)

    y -= 6
    y = _new_page_if_needed(c, y)

    # SEO details
    y = _draw_subheading(c, "SEO Findings", x, y)
    on_page = seo.get("on_page_issues") or []
    tech = seo.get("technical_issues") or []
    gaps = seo.get("content_gaps") or []

    if on_page:
        y = _draw_paragraph(c, "On-page issues:", x, y)
        y = _draw_bullets(c, [ _safe_str(i) for i in on_page ], x + 12, y, max_items=12)
    if tech:
        y = _draw_paragraph(c, "Technical issues:", x, y)
        y = _draw_bullets(c, [ _safe_str(i) for i in tech ], x + 12, y, max_items=12)
    if gaps:
        y = _draw_paragraph(c, "Content gaps:", x, y)
        y = _draw_bullets(c, [ _safe_str(i) for i in gaps ], x + 12, y, max_items=12)

    y -= 6
    y = _new_page_if_needed(c, y)

    # Performance details
    y = _draw_subheading(c, "Performance Findings", x, y)
    page_size_issues = (perf.get("page_size_issues") or [])
    if page_size_issues:
        y = _draw_paragraph(c, "Page-size / load issues:", x, y)
        y = _draw_bullets(c, [ _safe_str(i) for i in page_size_issues ], x + 12, y, max_items=12)

    y -= 6
    y = _new_page_if_needed(c, y)

    # Mobile
    y = _draw_subheading(c, "Mobile Findings", x, y)
    mobile_issues = (mobile.get("mobile_usability_problems") or []) + (mobile.get("responsive_issues") or [])
    if mobile_issues:
        y = _draw_bullets(c, [ _safe_str(i) for i in mobile_issues ], x, y, max_items=12)
    else:
        y = _draw_paragraph(c, "No mobile-specific issues were provided by the runner output.", x, y)

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.grey)
    c.drawString(x, 30, "Generated by FF Tech Audit System")

    c.save()
    return output_path
