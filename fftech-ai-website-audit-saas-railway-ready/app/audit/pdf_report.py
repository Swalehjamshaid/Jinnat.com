# -*- coding: utf-8 -*-
"""
app/audit/pdf_report.py

World-class 5-page PDF builder for Website Audit output.

- Produces a structured, branded, 5-page report
- Colored charts (matplotlib) embedded into ReportLab
- Professional layout: cover, exec summary, deep dive, security/links, action plan & appendix
- Does not alter runner output (no loss of input/output)

Expected runner_result keys (best-effort):
  audited_url, overall_score, grade, breakdown, dynamic, chart_data
"""

from __future__ import annotations

import os
import io
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
)

# Matplotlib (headless)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ----------------------------
# Branding / Theme
# ----------------------------
BRAND = {
    "primary": colors.HexColor("#4F46E5"),      # Indigo
    "primary_dark": colors.HexColor("#4338CA"),
    "accent": colors.HexColor("#10B981"),       # Emerald
    "warning": colors.HexColor("#F59E0B"),      # Amber
    "danger": colors.HexColor("#EF4444"),       # Red
    "info": colors.HexColor("#06B6D4"),         # Cyan
    "bg_soft": colors.HexColor("#F8FAFC"),      # Slate-50
    "text": colors.HexColor("#0F172A"),         # Slate-900
    "muted": colors.HexColor("#475569"),        # Slate-600
    "border": colors.HexColor("#E2E8F0"),       # Slate-200
}

A4_W, A4_H = A4


@dataclass
class PdfMeta:
    report_title: str
    brand_name: str
    client_name: str
    audit_date: str
    website_name: Optional[str]
    audited_url: str
    logo_path: Optional[str] = None


# ----------------------------
# Helpers
# ----------------------------
def _safe(v: Any, default="—") -> str:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        # Keep simple formatting
        if isinstance(v, float) and not math.isfinite(v):
            return default
        return str(v)
    s = str(v).strip()
    return s if s else default


def _num(v: Any, default=0.0) -> float:
    try:
        x = float(v)
        if not math.isfinite(x):
            return float(default)
        return x
    except Exception:
        return float(default)


def _grade_color(grade: str):
    g = (grade or "").upper().strip()
    if g.startswith("A"):
        return BRAND["accent"]
    if g.startswith("B"):
        return BRAND["info"]
    if g.startswith("C"):
        return BRAND["warning"]
    return BRAND["danger"]


def _score_to_label(score: float) -> str:
    if score >= 90: return "Excellent"
    if score >= 75: return "Good"
    if score >= 60: return "Fair"
    return "Needs Improvement"


def _risk_level(score: float) -> str:
    # Higher score => lower risk
    if score >= 85: return "Low"
    if score >= 70: return "Medium"
    return "High"


def _risk_color(risk: str):
    r = (risk or "").lower()
    if r == "low": return BRAND["accent"]
    if r == "medium": return BRAND["warning"]
    return BRAND["danger"]


def _extract_breakdown(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    b = result.get("breakdown") or {}
    # Normalize expected keys
    return {
        "seo": b.get("seo") or {},
        "performance": b.get("performance") or {},
        "links": b.get("links") or {},
        "security": b.get("security") or {},
        "ai": b.get("ai") or {},
        "competitors": b.get("competitors") or {},
    }


def _top_findings_from_extras(extras: Optional[Dict[str, Any]], max_items: int = 6) -> List[str]:
    """
    Convert extras dict into bullet-like findings.
    This is best-effort since runner extras vary by implementation.
    """
    if not extras or not isinstance(extras, dict):
        return ["No detailed signals returned by the scanner."]
    items = []
    for k, v in list(extras.items())[:max_items]:
        key = str(k).replace("_", " ").strip().title()
        if isinstance(v, bool):
            items.append(f"{key}: {'Yes' if v else 'No'}")
        else:
            items.append(f"{key}: {_safe(v)}")
    return items or ["No detailed signals returned by the scanner."]


# ----------------------------
# Chart Builders (matplotlib -> PNG bytes)
# ----------------------------
def _fig_to_png_bytes(fig) -> bytes:
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=180, bbox_inches="tight", transparent=False)
    plt.close(fig)
    bio.seek(0)
    return bio.read()


def build_category_bar_chart(scores: Dict[str, float]) -> bytes:
    labels = ["SEO", "Performance", "Links", "Security", "AI", "Competitors"]
    values = [scores.get("seo", 0), scores.get("performance", 0), scores.get("links", 0),
              scores.get("security", 0), scores.get("ai", 0), scores.get("competitors", 0)]
    cols = ["#F59E0B", "#06B6D4", "#10B981", "#EF4444", "#3B82F6", "#8B5CF6"]

    fig = plt.figure(figsize=(8.2, 3.2))
    ax = fig.add_subplot(111)
    ax.bar(labels, values, color=cols, edgecolor="#111827", linewidth=0.4)
    ax.set_ylim(0, 100)
    ax.set_title("Category Score Breakdown", fontsize=12, weight="bold")
    ax.grid(axis="y", alpha=0.18)
    for i, v in enumerate(values):
        ax.text(i, v + 2, f"{int(v)}", ha="center", va="bottom", fontsize=9, weight="bold")
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def build_radar_chart(scores: Dict[str, float]) -> bytes:
    labels = ["SEO", "Performance", "Links", "Security", "AI", "Competitors"]
    vals = [scores.get("seo", 0), scores.get("performance", 0), scores.get("links", 0),
            scores.get("security", 0), scores.get("ai", 0), scores.get("competitors", 0)]
    vals += vals[:1]
    angles = [n / float(len(labels)) * 2 * math.pi for n in range(len(labels))]
    angles += angles[:1]

    fig = plt.figure(figsize=(6.2, 4.2))
    ax = plt.subplot(111, polar=True)
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids([a * 180 / math.pi for a in angles[:-1]], labels, fontsize=9)

    ax.set_ylim(0, 100)
    ax.plot(angles, vals, linewidth=2, color="#4F46E5")
    ax.fill(angles, vals, color="#4F46E5", alpha=0.20)
    ax.set_title("Audit Radar (Higher is Better)", fontsize=12, weight="bold", pad=18)
    ax.grid(alpha=0.20)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def build_gauge_like_donut(overall_score: float) -> bytes:
    score = max(0, min(100, float(overall_score)))
    fig = plt.figure(figsize=(3.4, 3.4))
    ax = fig.add_subplot(111)
    ax.axis("equal")

    # Donut
    sizes = [score, 100 - score]
    col_main = "#10B981" if score >= 85 else "#06B6D4" if score >= 70 else "#F59E0B" if score >= 55 else "#EF4444"
    ax.pie(
        sizes,
        startangle=90,
        colors=[col_main, "#E5E7EB"],
        wedgeprops=dict(width=0.28, edgecolor="white")
    )
    ax.text(0, 0.02, f"{int(score)}", ha="center", va="center", fontsize=26, weight="bold", color="#111827")
    ax.text(0, -0.22, _score_to_label(score), ha="center", va="center", fontsize=10, color="#475569")
    ax.set_title("Overall Score", fontsize=11, weight="bold", pad=10)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


# ----------------------------
# PDF Builder
# ----------------------------
def generate_worldclass_5page_pdf(
    runner_result: Dict[str, Any],
    output_path: str,
    *,
    logo_path: Optional[str] = None,
    report_title: str = "Website Audit Report",
    client_name: str = "N/A",
    brand_name: str = "FF Tech",
    audit_date: str = "",
    website_name: Optional[str] = None,
) -> str:
    """
    Main entry: creates a 5-page PDF at output_path.
    """
    audited_url = _safe(runner_result.get("audited_url"), "website")
    meta = PdfMeta(
        report_title=report_title,
        brand_name=brand_name,
        client_name=client_name,
        audit_date=_safe(audit_date, ""),
        website_name=website_name,
        audited_url=audited_url,
        logo_path=logo_path,
    )

    breakdown = _extract_breakdown(runner_result)
    overall_score = _num(runner_result.get("overall_score"), 0)
    grade = _safe(runner_result.get("grade"), "—")

    scores = {
        "seo": _num(breakdown["seo"].get("score"), 0),
        "performance": _num(breakdown["performance"].get("score"), 0),
        "links": _num(breakdown["links"].get("score"), 0),
        "security": _num(breakdown["security"].get("score"), 0),
        "ai": _num(breakdown["ai"].get("score"), 0),
        "competitors": _num(breakdown["competitors"].get("score"), 0),
    }

    # Build charts once
    chart_bar = build_category_bar_chart(scores)
    chart_radar = build_radar_chart(scores)
    chart_donut = build_gauge_like_donut(overall_score)

    # Document setup
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=meta.report_title,
        author=meta.brand_name,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=BRAND["text"],
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=BRAND["text"],
        spaceBefore=8,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.2,
        leading=14,
        textColor=BRAND["text"],
    ))
    styles.add(ParagraphStyle(
        name="Muted",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=13,
        textColor=BRAND["muted"],
    ))
    styles.add(ParagraphStyle(
        name="Center",
        parent=styles["BodyText"],
        alignment=TA_CENTER,
        fontName="Helvetica",
        fontSize=10.2,
        textColor=BRAND["text"],
    ))
    styles.add(ParagraphStyle(
        name="Badge",
        parent=styles["BodyText"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.white,
    ))

    story: List[Any] = []

    # ---------- PAGE 1: COVER + EXEC SNAPSHOT ----------
    story.extend(_page1_cover(meta, overall_score, grade, chart_donut, styles, scores))

    # ---------- PAGE 2: EXEC SUMMARY + CATEGORY CHART ----------
    story.append(PageBreak())
    story.extend(_page2_exec_summary(meta, overall_score, grade, chart_bar, chart_radar, styles, scores))

    # ---------- PAGE 3: SEO + PERFORMANCE DEEP DIVE ----------
    story.append(PageBreak())
    story.extend(_page3_seo_perf(breakdown, styles))

    # ---------- PAGE 4: SECURITY + LINKS + AI + COMPETITORS ----------
    story.append(PageBreak())
    story.extend(_page4_security_links_ai_comp(breakdown, styles, scores))

    # ---------- PAGE 5: ACTION PLAN + APPENDIX ----------
    story.append(PageBreak())
    story.extend(_page5_action_plan_appendix(runner_result, breakdown, styles, scores))

    # Ensure exactly 5 pages: we build precisely with 4 PageBreaks.
    def on_first_page(canvas, doc_):
        _draw_header_footer(canvas, doc_, meta, page_num=1, total_pages=5, is_cover=True)

    def on_later_pages(canvas, doc_):
        # doc_.page is current page number
        _draw_header_footer(canvas, doc_, meta, page_num=doc_.page, total_pages=5, is_cover=False)

    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    return output_path


# ----------------------------
# Page Builders
# ----------------------------
def _page1_cover(meta: PdfMeta, overall_score: float, grade: str, donut_png: bytes, styles, scores):
    elems = []

    # Brand ribbon
    elems.append(Spacer(1, 6 * mm))
    elems.append(Paragraph(f"<b>{meta.brand_name}</b> • Website Audit Report", styles["Muted"]))
    elems.append(Spacer(1, 6 * mm))

    title = meta.report_title or "Website Audit Report"
    elems.append(Paragraph(title, styles["H1"]))
    sub = meta.website_name or meta.audited_url
    elems.append(Paragraph(f"<b>Audited Property:</b> {sub}", styles["Body"]))
    elems.append(Paragraph(f"<b>Client:</b> {_safe(meta.client_name)}", styles["Body"]))
    elems.append(Paragraph(f"<b>Date:</b> {_safe(meta.audit_date)}", styles["Body"]))
    elems.append(Spacer(1, 10 * mm))

    # Score block (donut + grade badge + key bullets)
    donut_img = Image(io.BytesIO(donut_png), width=70*mm, height=70*mm)
    donut_img.hAlign = "LEFT"

    gcol = _grade_color(grade)
    badge = Table([[Paragraph(f"Grade: {grade}", styles["Badge"])]], colWidths=[55*mm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), gcol),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("BOX", (0,0), (-1,-1), 0.5, colors.white),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))

    summary_bullets = [
        f"Overall Score: <b>{int(overall_score)}</b> ({_score_to_label(overall_score)})",
        f"SEO: <b>{int(scores.get('seo',0))}</b> • Performance: <b>{int(scores.get('performance',0))}</b>",
        f"Security: <b>{int(scores.get('security',0))}</b> • Links: <b>{int(scores.get('links',0))}</b>",
        f"AI Readiness: <b>{int(scores.get('ai',0))}</b> • Competitors: <b>{int(scores.get('competitors',0))}</b>",
    ]
    bullets_html = "<br/>".join([f"• {b}" for b in summary_bullets])
    bullets = Paragraph(bullets_html, styles["Body"])

    layout = Table(
        [[donut_img, Spacer(1, 1), KeepTogether([badge, Spacer(1, 3*mm), bullets])]],
        colWidths=[78*mm, 6*mm, 90*mm]
    )
    layout.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    elems.append(layout)

    elems.append(Spacer(1, 10*mm))

    # Professional note
    note = (
        "This report provides a structured assessment across SEO, Performance, Security, Links, "
        "AI Readiness and Competitive Positioning. Scores represent the scanner’s automated signals "
        "and are intended to guide prioritization."
    )
    elems.append(Paragraph(note, styles["Muted"]))

    return elems


def _page2_exec_summary(meta: PdfMeta, overall_score: float, grade: str,
                        bar_png: bytes, radar_png: bytes, styles, scores):
    elems = []
    elems.append(Paragraph("Executive Summary", styles["H1"]))
    elems.append(Paragraph(
        f"This section summarizes the audit outcome for <b>{meta.audited_url}</b> "
        f"with an overall score of <b>{int(overall_score)}</b> (Grade <b>{grade}</b>).",
        styles["Body"]
    ))
    elems.append(Spacer(1, 6*mm))

    # Charts row
    img_bar = Image(io.BytesIO(bar_png), width=165*mm, height=62*mm)
    img_radar = Image(io.BytesIO(radar_png), width=165*mm, height=85*mm)
    img_bar.hAlign = "CENTER"
    img_radar.hAlign = "CENTER"

    elems.append(Paragraph("Score Visualizations", styles["H2"]))
    elems.append(img_bar)
    elems.append(Spacer(1, 3*mm))
    elems.append(img_radar)
    elems.append(Spacer(1, 6*mm))

    # Score table with risk
    rows = [["Category", "Score", "Risk", "Interpretation"]]
    for key, label in [
        ("seo", "SEO"),
        ("performance", "Performance"),
        ("security", "Security"),
        ("links", "Links"),
        ("ai", "AI Readiness"),
        ("competitors", "Competitors"),
    ]:
        sc = float(scores.get(key, 0))
        risk = _risk_level(sc)
        rows.append([label, f"{int(sc)}", risk, _score_to_label(sc)])

    t = Table(rows, colWidths=[40*mm, 25*mm, 25*mm, 75*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BRAND["primary"]),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 10),
        ("ALIGN", (1,1), (2,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.25, BRAND["border"]),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, BRAND["bg_soft"]]),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))

    # Color risk cells
    for i in range(1, len(rows)):
        rc = _risk_color(rows[i][2])
        t.setStyle(TableStyle([
            ("TEXTCOLOR", (2,i), (2,i), rc),
            ("FONTNAME", (2,i), (2,i), "Helvetica-Bold"),
        ]))

    elems.append(Paragraph("Category Summary Table", styles["H2"]))
    elems.append(t)
    elems.append(Spacer(1, 6*mm))

    elems.append(Paragraph("Methodology (High-Level)", styles["H2"]))
    elems.append(Paragraph(
        "The audit engine fetches the page, inspects headers & markup, extracts SEO and technical signals, "
        "scores categories, and consolidates findings into actionable guidance.",
        styles["Body"]
    ))
    elems.append(Paragraph(
        "Note: Results are based on the scanned URL and may vary with different pages, geo/CDN routing, "
        "authentication requirements, or dynamic rendering behavior.",
        styles["Muted"]
    ))

    return elems


def _page3_seo_perf(breakdown: Dict[str, Dict[str, Any]], styles):
    elems = []
    elems.append(Paragraph("Deep Dive: SEO & Performance", styles["H1"]))

    seo = breakdown.get("seo") or {}
    perf = breakdown.get("performance") or {}

    seo_score = _num(seo.get("score"), 0)
    perf_score = _num(perf.get("score"), 0)

    elems.append(Paragraph("SEO Assessment", styles["H2"]))
    elems.append(Paragraph(
        f"SEO score is <b>{int(seo_score)}</b>. This reflects discoverability signals including metadata, "
        f"indexing hints, and content structure signals returned by the scanner.",
        styles["Body"]
    ))
    seo_findings = _top_findings_from_extras(seo.get("extras"))
    elems.append(_bullets_block("Top SEO Signals Observed", seo_findings, styles))

    elems.append(Spacer(1, 6*mm))

    elems.append(Paragraph("Performance Assessment", styles["H2"]))
    elems.append(Paragraph(
        f"Performance score is <b>{int(perf_score)}</b>. This reflects load footprint and render‑related signals "
        f"captured by the scanner output.",
        styles["Body"]
    ))
    perf_findings = _top_findings_from_extras(perf.get("extras"))
    elems.append(_bullets_block("Top Performance Signals Observed", perf_findings, styles))

    elems.append(Spacer(1, 6*mm))
    elems.append(Paragraph("Recommended Improvements (Priority)", styles["H2"]))

    recs = [
        "Fix critical indexing/metadata issues (titles, descriptions, canonical) where missing or inconsistent.",
        "Improve Core Web footprint: reduce page weight, minimize render‑blocking assets, compress images.",
        "Ensure structured content hierarchy (H1/H2) and add schema markup where relevant.",
        "Enable caching policies and optimize resource delivery (CDN, compression, HTTP/2).",
    ]
    elems.append(_bullets_block("High Impact Actions", recs, styles))

    return elems


def _page4_security_links_ai_comp(breakdown: Dict[str, Dict[str, Any]], styles, scores: Dict[str, float]):
    elems = []
    elems.append(Paragraph("Deep Dive: Security, Links, AI & Competitors", styles["H1"]))

    sec = breakdown.get("security") or {}
    links = breakdown.get("links") or {}
    ai = breakdown.get("ai") or {}
    comp = breakdown.get("competitors") or {}

    elems.append(Paragraph("Security & Headers", styles["H2"]))
    elems.append(Paragraph(
        f"Security score is <b>{int(scores.get('security',0))}</b>. This section summarizes transport security "
        f"and header-level hardening signals.",
        styles["Body"]
    ))

    # Security table
    rows = [["Signal", "Value"]]
    rows.append(["HTTPS", "Yes" if sec.get("https") else "No"])
    rows.append(["HSTS", "Yes" if sec.get("hsts") else "No"])
    rows.append(["Status Code", _safe(sec.get("status_code"))])
    rows.append(["Server", _safe(sec.get("server"))])

    t = Table(rows, colWidths=[55*mm, 110*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BRAND["primary"]),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, BRAND["border"]),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, BRAND["bg_soft"]]),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 6*mm))

    elems.append(Paragraph("Links Health", styles["H2"]))
    elems.append(Paragraph(
        f"Links score is <b>{int(scores.get('links',0))}</b>. This section summarizes internal and external link footprint.",
        styles["Body"]
    ))
    elems.append(Paragraph(
        f"<b>Internal:</b> {_safe(links.get('internal_links_count', 0))} • "
        f"<b>External:</b> {_safe(links.get('external_links_count', 0))} • "
        f"<b>Total:</b> {_safe(links.get('total_links_count', 0))}",
        styles["Body"]
    ))

    elems.append(Spacer(1, 6*mm))
    elems.append(Paragraph("AI Readiness & Competitors", styles["H2"]))
    elems.append(Paragraph(
        f"AI readiness score: <b>{int(scores.get('ai',0))}</b> • Competitors score: <b>{int(scores.get('competitors',0))}</b>.",
        styles["Body"]
    ))
    tc = comp.get("top_competitor_score")
    if tc is not None:
        elems.append(Paragraph(f"<b>Top competitor benchmark score:</b> {_safe(tc)}", styles["Body"]))
    else:
        elems.append(Paragraph("Benchmark data not available in this run.", styles["Muted"]))

    elems.append(Spacer(1, 6*mm))
    elems.append(Paragraph("Risk Notes", styles["H2"]))
    risk_notes = [
        "If HTTPS or HSTS is missing, prioritize transport hardening to reduce interception risk.",
        "Investigate excessive external links or broken internal navigation to improve crawl quality.",
        "Improve structured metadata to support AI assistants and rich preview engines.",
    ]
    elems.append(_bullets_block("Key Risk & Compliance Considerations", risk_notes, styles))
    return elems


def _page5_action_plan_appendix(result: Dict[str, Any], breakdown: Dict[str, Dict[str, Any]], styles, scores: Dict[str, float]):
    elems = []
    elems.append(Paragraph("Action Plan & Technical Appendix", styles["H1"]))

    elems.append(Paragraph("Prioritized Action Plan (Next 30 Days)", styles["H2"]))
    plan = [
        "P0 (0–3 days): Fix critical security issues (HTTPS/HSTS), broken redirects, and missing core metadata.",
        "P1 (1–2 weeks): Reduce page weight, remove render-blocking assets, and optimize caching/compression.",
        "P2 (2–4 weeks): Enhance structured data, improve content hierarchy, and strengthen internal linking.",
        "P3 (ongoing): Monitor competitors and iterate content for SEO + AI search readiness.",
    ]
    elems.append(_bullets_block("Implementation Roadmap", plan, styles))
    elems.append(Spacer(1, 6*mm))

    elems.append(Paragraph("Technical Appendix (Signals & Metadata)", styles["H2"]))
    dyn = result.get("dynamic") or {}
    kv = dyn.get("kv") or []

    if kv and isinstance(kv, list):
        # Show top 14 KV pairs to fit on one page, but keep “world-class” readability
        rows = [["Key", "Value"]]
        for item in kv[:14]:
            rows.append([_safe(item.get("key")), _safe(item.get("value"))])

        t = Table(rows, colWidths=[55*mm, 110*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), BRAND["primary"]),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.25, BRAND["border"]),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, BRAND["bg_soft"]]),
            ("FONTSIZE", (0,1), (-1,-1), 9),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        elems.append(t)
    else:
        elems.append(Paragraph("No KV metadata was returned in this run.", styles["Muted"]))

    elems.append(Spacer(1, 5*mm))
    elems.append(Paragraph("Limitations & Disclaimer", styles["H2"]))
    elems.append(Paragraph(
        "This report is generated by an automated scanner. Results depend on the scanned URL, "
        "network conditions, and the content served at scan time. For critical security posture, "
        "a full manual penetration assessment is recommended.",
        styles["Muted"]
    ))
    elems.append(Spacer(1, 3*mm))
    elems.append(Paragraph(
        f"<b>Prepared by:</b> { _safe(result.get('engine') , 'FF Tech Audit Engine') }",
        styles["Muted"]
    ))

    return elems


def _bullets_block(title: str, bullets: List[str], styles):
    safe_bullets = bullets or []
    html = "<br/>".join([f"• {b}" for b in safe_bullets])
    card = Table(
        [[Paragraph(f"<b>{title}</b>", styles["Body"])],
         [Paragraph(html, styles["Body"])]],
        colWidths=[170*mm]
    )
    card.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BRAND["bg_soft"]),
        ("BOX", (0,0), (-1,-1), 0.6, BRAND["border"]),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    return card


# ----------------------------
# Header/Footer
# ----------------------------
def _draw_header_footer(canvas, doc, meta: PdfMeta, page_num: int, total_pages: int, is_cover: bool):
    canvas.saveState()

    # Top bar
    bar_h = 12 * mm if not is_cover else 14 * mm
    canvas.setFillColor(BRAND["primary"])
    canvas.rect(0, A4_H - bar_h, A4_W, bar_h, stroke=0, fill=1)

    # Brand text
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(18 * mm, A4_H - 8.5 * mm, meta.brand_name)

    # Title right
    canvas.setFont("Helvetica", 9.5)
    title = meta.report_title[:60]
    tw = stringWidth(title, "Helvetica", 9.5)
    canvas.drawString(A4_W - 18*mm - tw, A4_H - 8.5 * mm, title)

    # Footer line
    canvas.setStrokeColor(BRAND["border"])
    canvas.setLineWidth(0.6)
    canvas.line(18*mm, 14*mm, A4_W - 18*mm, 14*mm)

    # Footer text
    canvas.setFillColor(BRAND["muted"])
    canvas.setFont("Helvetica", 8.8)
    canvas.drawString(18*mm, 8*mm, f"Audited URL: {meta.audited_url}")

    # Page number
    canvas.setFont("Helvetica-Bold", 8.8)
    canvas.drawRightString(A4_W - 18*mm, 8*mm, f"Page {page_num} of {total_pages}")

    canvas.restoreState()
