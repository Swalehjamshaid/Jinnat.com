# -*- coding: utf-8 -*-
"""
app/audit/pdf_report.py

International-standard, world-class 5-page PDF builder for Website Audit output.

Goals:
- Beautiful, executive-grade PDF with charts and strong typography
- Robust in production (Railway/Docker/Linux)
- Defensive coding: missing fields should NOT crash PDF generation
- Strict output: capped content to avoid accidental page overflow
- Does NOT change runner_result I/O schema (no loss of input/output)

Expected runner_result keys (best-effort):
  audited_url, overall_score, grade, breakdown, dynamic, chart_data
"""

from __future__ import annotations

import io
import os
import math
import datetime as _dt
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple

# ----------------------------
# Matplotlib (headless + safe cache)
# ----------------------------
# Railway sometimes blocks default matplotlib cache dir.
# You can also set env var: MPLCONFIGDIR=/tmp/matplotlib
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib  # noqa: E402
matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

# ----------------------------
# ReportLab
# ----------------------------
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether,
)

A4_W, A4_H = A4

# =========================================================
# Branding / Theme (tweak here for your brand)
# =========================================================
BRAND = {
    "primary": colors.HexColor("#4F46E5"),       # Indigo
    "primary_dark": colors.HexColor("#4338CA"),
    "accent": colors.HexColor("#10B981"),        # Emerald
    "warning": colors.HexColor("#F59E0B"),       # Amber
    "danger": colors.HexColor("#EF4444"),        # Red
    "info": colors.HexColor("#06B6D4"),          # Cyan
    "purple": colors.HexColor("#8B5CF6"),
    "blue": colors.HexColor("#3B82F6"),

    "bg_soft": colors.HexColor("#F8FAFC"),       # Slate-50
    "bg_card": colors.HexColor("#FFFFFF"),
    "text": colors.HexColor("#0F172A"),          # Slate-900
    "muted": colors.HexColor("#475569"),         # Slate-600
    "border": colors.HexColor("#E2E8F0"),        # Slate-200
    "grid": colors.HexColor("#CBD5E1"),          # Slate-300
}

# =========================================================
# Output Guardrails (keep report strictly 5 pages)
# =========================================================
CAPS = {
    "max_exec_bullets": 6,
    "max_top_risks": 6,
    "max_quick_wins": 6,
    "max_extras_findings": 7,
    "max_dynamic_cards": 6,
    "max_kv_rows": 14,
    "max_raw_json_chars": 2200,  # keep appendix stable
}


@dataclass
class PdfMeta:
    report_title: str
    brand_name: str
    client_name: str
    audit_date: str
    website_name: Optional[str]
    audited_url: str
    logo_path: Optional[str] = None


# =========================================================
# Helper: safe conversions
# =========================================================
def _safe(v: Any, default: str = "—") -> str:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not math.isfinite(v):
            return default
        # keep as int if close
        if isinstance(v, float) and abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return str(v)
    s = str(v).strip()
    return s if s else default


def _num(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if not math.isfinite(x):
            return float(default)
        return x
    except Exception:
        return float(default)


def _clamp_score(x: float) -> float:
    return max(0.0, min(100.0, float(x)))


def _today_stamp() -> str:
    return _dt.date.today().isoformat()


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
    s = _clamp_score(score)
    if s >= 90:
        return "Excellent"
    if s >= 75:
        return "Good"
    if s >= 60:
        return "Fair"
    return "Needs Improvement"


def _risk_level(score: float) -> str:
    # Higher score => lower risk
    s = _clamp_score(score)
    if s >= 85:
        return "Low"
    if s >= 70:
        return "Medium"
    return "High"


def _risk_color(risk: str):
    r = (risk or "").lower()
    if r == "low":
        return BRAND["accent"]
    if r == "medium":
        return BRAND["warning"]
    return BRAND["danger"]


def _extract_breakdown(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    b = result.get("breakdown") or {}
    return {
        "seo": b.get("seo") or {},
        "performance": b.get("performance") or {},
        "links": b.get("links") or {},
        "security": b.get("security") or {},
        "ai": b.get("ai") or {},
        "competitors": b.get("competitors") or {},
        # Optional keys you might add later
        "accessibility": b.get("accessibility") or {},
        "content": b.get("content") or {},
    }


# =========================================================
# Helper: interpret extras into readable bullets
# =========================================================
def _top_findings_from_extras(extras: Optional[Dict[str, Any]], max_items: int = 7) -> List[str]:
    """
    Convert extras dict into bullet-like findings.
    Defensive: works with dicts, nested dicts (partial), and primitives.
    """
    if not extras or not isinstance(extras, dict):
        return ["No detailed signals returned by the scanner for this section."]

    items: List[str] = []
    for k, v in list(extras.items()):
        if len(items) >= max_items:
            break
        key = str(k).replace("_", " ").strip().title()

        if isinstance(v, bool):
            items.append(f"{key}: {'Yes' if v else 'No'}")
        elif isinstance(v, (int, float, str)):
            items.append(f"{key}: {_safe(v)}")
        elif isinstance(v, dict):
            # take 1-2 subkeys
            subparts = []
            for sk, sv in list(v.items())[:2]:
                subparts.append(f"{str(sk).replace('_',' ')}={_safe(sv)}")
            if subparts:
                items.append(f"{key}: " + ", ".join(subparts))
            else:
                items.append(f"{key}: Available")
        elif isinstance(v, list):
            items.append(f"{key}: {len(v)} items")
        else:
            items.append(f"{key}: Available")

    return items or ["No detailed signals returned by the scanner for this section."]


# =========================================================
# Charts (matplotlib -> PNG bytes)
# =========================================================
def _fig_to_png_bytes(fig) -> bytes:
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=180, bbox_inches="tight", transparent=False)
    plt.close(fig)
    bio.seek(0)
    return bio.read()


def build_category_bar_chart(scores: Dict[str, float]) -> bytes:
    labels = ["SEO", "Performance", "Links", "Security", "AI", "Competitors"]
    values = [
        _clamp_score(scores.get("seo", 0)),
        _clamp_score(scores.get("performance", 0)),
        _clamp_score(scores.get("links", 0)),
        _clamp_score(scores.get("security", 0)),
        _clamp_score(scores.get("ai", 0)),
        _clamp_score(scores.get("competitors", 0)),
    ]
    cols = ["#F59E0B", "#06B6D4", "#10B981", "#EF4444", "#3B82F6", "#8B5CF6"]

    fig = plt.figure(figsize=(8.4, 3.3))
    ax = fig.add_subplot(111)
    ax.bar(labels, values, color=cols, edgecolor="#111827", linewidth=0.4)
    ax.set_ylim(0, 100)
    ax.set_title("Category Score Breakdown (0-100)", fontsize=12, weight="bold")
    ax.grid(axis="y", alpha=0.18)
    for i, v in enumerate(values):
        ax.text(i, v + 2, f"{int(round(v))}", ha="center", va="bottom", fontsize=9, weight="bold")
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def build_radar_chart(scores: Dict[str, float]) -> bytes:
    labels = ["SEO", "Performance", "Links", "Security", "AI", "Competitors"]
    vals = [
        _clamp_score(scores.get("seo", 0)),
        _clamp_score(scores.get("performance", 0)),
        _clamp_score(scores.get("links", 0)),
        _clamp_score(scores.get("security", 0)),
        _clamp_score(scores.get("ai", 0)),
        _clamp_score(scores.get("competitors", 0)),
    ]
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
    ax.fill(angles, vals, color="#4F46E5", alpha=0.22)
    ax.set_title("Audit Radar (Higher is Better)", fontsize=12, weight="bold", pad=18)
    ax.grid(alpha=0.20)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def build_gauge_like_donut(overall_score: float) -> bytes:
    score = _clamp_score(overall_score)
    fig = plt.figure(figsize=(3.6, 3.6))
    ax = fig.add_subplot(111)
    ax.axis("equal")

    sizes = [score, 100 - score]
    col_main = "#10B981" if score >= 85 else "#06B6D4" if score >= 70 else "#F59E0B" if score >= 55 else "#EF4444"
    ax.pie(
        sizes,
        startangle=90,
        colors=[col_main, "#E5E7EB"],
        wedgeprops=dict(width=0.30, edgecolor="white"),
    )
    ax.text(0, 0.02, f"{int(round(score))}", ha="center", va="center", fontsize=26, weight="bold", color="#111827")
    ax.text(0, -0.25, _score_to_label(score), ha="center", va="center", fontsize=10, color="#475569")
    ax.set_title("Overall Score", fontsize=11, weight="bold", pad=10)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


# =========================================================
# Layout helpers
# =========================================================
def _load_logo(logo_path: Optional[str], max_w_mm: float = 32.0, max_h_mm: float = 12.0) -> Optional[Image]:
    """
    Load logo if exists. Never crash if missing/unreadable.
    """
    if not logo_path:
        return None
    try:
        p = logo_path.strip()
        if not p:
            return None
        # if relative, accept as-is; caller may provide absolute path
        if not os.path.isfile(p):
            return None
        img = Image(p)
        img.drawWidth = max_w_mm * mm
        img.drawHeight = max_h_mm * mm
        img.hAlign = "LEFT"
        return img
    except Exception:
        return None


def _chip(text: str, bg, fg=colors.white) -> Table:
    t = Table([[Paragraph(f"<b>{text}</b>", ParagraphStyle(
        "chip",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=fg,
        alignment=TA_CENTER,
        leading=11
    ))]], colWidths=[46 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _card(title: str, body: List[Any], styles, accent_color=BRAND["primary"]) -> Table:
    """
    A consistent card container (international report style).
    """
    header = Table([[Paragraph(f"<b>{title}</b>", styles["CardTitle"])]], colWidths=[170 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND["bg_soft"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, accent_color),
    ]))

    content = Table([[body]], colWidths=[170 * mm])
    content.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND["bg_card"]),
        ("BOX", (0, 0), (-1, -1), 0.6, BRAND["border"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    return Table([[header], [content]], colWidths=[170 * mm])


def _bullets(items: List[str], styles, max_items: int) -> Paragraph:
    items = (items or [])[:max_items]
    html = "<br/>".join([f"• {i}" for i in items]) if items else "—"
    return Paragraph(html, styles["Body"])


def _best_and_worst(scores: Dict[str, float]) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    pairs = [
        ("SEO", _clamp_score(scores.get("seo", 0))),
        ("Performance", _clamp_score(scores.get("performance", 0))),
        ("Links", _clamp_score(scores.get("links", 0))),
        ("Security", _clamp_score(scores.get("security", 0))),
        ("AI Readiness", _clamp_score(scores.get("ai", 0))),
        ("Competitors", _clamp_score(scores.get("competitors", 0))),
    ]
    best = sorted(pairs, key=lambda x: x[1], reverse=True)[:3]
    worst = sorted(pairs, key=lambda x: x[1])[:3]
    return best, worst


def _derive_top_risks(scores: Dict[str, float]) -> List[str]:
    """
    Simple, reliable risk statements based on low category scores.
    (Better than guessing unknown fields.)
    """
    risks = []
    if scores.get("security", 100) < 70:
        risks.append("Security posture appears below target. Prioritize HTTPS/HSTS and security header hardening.")
    if scores.get("performance", 100) < 70:
        risks.append("Performance signals indicate potential slow load/UX issues. Optimize page weight and render-blocking assets.")
    if scores.get("seo", 100) < 70:
        risks.append("SEO discoverability signals need improvement. Validate titles/descriptions/canonical and indexing directives.")
    if scores.get("links", 100) < 70:
        risks.append("Link health may impact crawl quality. Reduce broken links and improve internal navigation structure.")
    if scores.get("ai", 100) < 70:
        risks.append("AI readiness signals suggest missing structured content/metadata. Add schema and improve semantic structure.")
    if scores.get("competitors", 100) < 70:
        risks.append("Competitive positioning appears weak against benchmarks. Consider content strategy and UX improvements.")
    return (risks or ["No high-severity risks detected from category scoring."])[:CAPS["max_top_risks"]]


def _derive_quick_wins(breakdown: Dict[str, Dict[str, Any]], scores: Dict[str, float]) -> List[str]:
    wins = []
    seo_ex = (breakdown.get("seo") or {}).get("extras") or {}
    perf_ex = (breakdown.get("performance") or {}).get("extras") or {}
    sec = breakdown.get("security") or {}

    # Conservative quick wins (avoid guessing too much)
    if scores.get("seo", 100) < 85:
        wins.append("Ensure every page has a unique, concise title and meta description aligned to target keywords.")
    if scores.get("performance", 100) < 85:
        wins.append("Compress/resize images and enable long-lived caching for static assets (CSS/JS/images).")
    if not sec.get("hsts", False):
        wins.append("Enable HSTS (Strict-Transport-Security) to improve transport security (after HTTPS confirmed).")
    # Use extras hints if present
    if "canonical" in seo_ex and seo_ex.get("canonical") in (False, None, ""):
        wins.append("Add/validate canonical URL to reduce duplicate indexing and consolidate ranking signals.")
    if "load_ms" in perf_ex:
        wins.append("Reduce time-to-load by removing render-blocking scripts and deferring non-critical JS.")
    return (wins or ["No immediate quick wins detected from available signals."])[:CAPS["max_quick_wins"]]


# =========================================================
# Public API: PDF Builder
# =========================================================
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
    Create a strict 5-page PDF at output_path.

    Defensive:
    - Missing runner fields won't crash
    - content capped to avoid spilling beyond 5 pages
    """

    audited_url = _safe(runner_result.get("audited_url"), "website")
    meta = PdfMeta(
        report_title=_safe(report_title, "Website Audit Report"),
        brand_name=_safe(brand_name, "FF Tech"),
        client_name=_safe(client_name, "N/A"),
        audit_date=_safe(audit_date, _today_stamp()),
        website_name=website_name,
        audited_url=audited_url,
        logo_path=logo_path,
    )

    breakdown = _extract_breakdown(runner_result)
    overall_score = _clamp_score(_num(runner_result.get("overall_score"), 0))
    grade = _safe(runner_result.get("grade"), "—")

    scores = {
        "seo": _clamp_score(_num((breakdown["seo"].get("score")), 0)),
        "performance": _clamp_score(_num((breakdown["performance"].get("score")), 0)),
        "links": _clamp_score(_num((breakdown["links"].get("score")), 0)),
        "security": _clamp_score(_num((breakdown["security"].get("score")), 0)),
        "ai": _clamp_score(_num((breakdown["ai"].get("score")), 0)),
        "competitors": _clamp_score(_num((breakdown["competitors"].get("score")), 0)),
    }

    # Build charts once (safe)
    chart_bar = build_category_bar_chart(scores)
    chart_radar = build_radar_chart(scores)
    chart_donut = build_gauge_like_donut(overall_score)

    # Styles
    styles = _build_styles()

    # Document setup (tight, professional margins)
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

    story: List[Any] = []

    # ===== PAGE 1: Cover + Executive Snapshot =====
    story.extend(_page1_cover(meta, overall_score, grade, chart_donut, styles, scores))

    # ===== PAGE 2: Executive Summary + Visuals + Risk =====
    story.append(PageBreak())
    story.extend(_page2_exec_summary(meta, overall_score, grade, chart_bar, chart_radar, styles, scores, breakdown))

    # ===== PAGE 3: SEO Deep Dive =====
    story.append(PageBreak())
    story.extend(_page3_seo_deep_dive(meta, breakdown, styles, scores))

    # ===== PAGE 4: Performance + Security Deep Dive =====
    story.append(PageBreak())
    story.extend(_page4_perf_security(meta, breakdown, styles, scores))

    # ===== PAGE 5: Links + AI + Competitors + Action Plan + Appendix =====
    story.append(PageBreak())
    story.extend(_page5_links_ai_action_appendix(meta, runner_result, breakdown, styles, scores))

    # Build with branded header/footer and page count
    doc.build(
        story,
        onFirstPage=lambda c, d: _draw_header_footer(c, d, meta, is_cover=True),
        onLaterPages=lambda c, d: _draw_header_footer(c, d, meta, is_cover=False),
    )

    return output_path


# =========================================================
# Styles (international report typography)
# =========================================================
def _build_styles():
    base = getSampleStyleSheet()

    # Avoid collisions if file is reloaded
    def add_style(style: ParagraphStyle):
        if style.name not in base.byName:
            base.add(style)

    add_style(ParagraphStyle(
        name="H1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=BRAND["text"],
        spaceAfter=8,
    ))
    add_style(ParagraphStyle(
        name="H2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13.5,
        leading=18,
        textColor=BRAND["text"],
        spaceBefore=8,
        spaceAfter=6,
    ))
    add_style(ParagraphStyle(
        name="H3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=15,
        textColor=BRAND["text"],
        spaceBefore=6,
        spaceAfter=4,
    ))
    add_style(ParagraphStyle(
        name="Body",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10.2,
        leading=14,
        textColor=BRAND["text"],
    ))
    add_style(ParagraphStyle(
        name="Muted",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=9.4,
        leading=13,
        textColor=BRAND["muted"],
    ))
    add_style(ParagraphStyle(
        name="Center",
        parent=base["BodyText"],
        alignment=TA_CENTER,
        fontName="Helvetica",
        fontSize=10.2,
        leading=14,
        textColor=BRAND["text"],
    ))
    add_style(ParagraphStyle(
        name="Right",
        parent=base["BodyText"],
        alignment=TA_RIGHT,
        fontName="Helvetica",
        fontSize=10.2,
        leading=14,
        textColor=BRAND["text"],
    ))
    add_style(ParagraphStyle(
        name="Badge",
        parent=base["BodyText"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        textColor=colors.white,
    ))
    add_style(ParagraphStyle(
        name="CardTitle",
        parent=base["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=BRAND["text"],
    ))

    return base


# =========================================================
# Page 1: Cover + Exec Snapshot
# =========================================================
def _page1_cover(meta: PdfMeta, overall_score: float, grade: str, donut_png: bytes, styles, scores: Dict[str, float]):
    elems: List[Any] = []

    logo = _load_logo(meta.logo_path)
    elems.append(Spacer(1, 6 * mm))

    # Top line (brand)
    if logo:
        header = Table([[logo, Paragraph(f"<b>{meta.brand_name}</b>", styles["Muted"])]], colWidths=[38*mm, 132*mm])
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        elems.append(header)
    else:
        elems.append(Paragraph(f"<b>{meta.brand_name}</b> • Website Audit Report", styles["Muted"]))

    elems.append(Spacer(1, 6 * mm))

    # Title & meta
    elems.append(Paragraph(_safe(meta.report_title), styles["H1"]))
    audited_name = meta.website_name or meta.audited_url
    elems.append(Paragraph(f"<b>Audited Property:</b> {_safe(audited_name)}", styles["Body"]))
    elems.append(Paragraph(f"<b>Client:</b> {_safe(meta.client_name)}", styles["Body"]))
    elems.append(Paragraph(f"<b>Audit Date:</b> {_safe(meta.audit_date)}", styles["Body"]))
    elems.append(Spacer(1, 10 * mm))

    donut_img = Image(io.BytesIO(donut_png), width=70*mm, height=70*mm)
    donut_img.hAlign = "LEFT"

    # Grade badge
    gcol = _grade_color(grade)
    badge = Table([[Paragraph(f"Grade: {grade}", styles["Badge"])]], colWidths=[55*mm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), gcol),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    best, worst = _best_and_worst(scores)
    best_txt = ", ".join([f"{k} {int(v)}" for k, v in best])
    worst_txt = ", ".join([f"{k} {int(v)}" for k, v in worst])

    chips = [
        _chip(f"Score: {int(round(overall_score))} / 100", BRAND["primary"]),
        _chip(f"Rating: {_score_to_label(overall_score)}", BRAND["info"]),
        _chip("Confidential", BRAND["danger"]),
    ]

    summary = [
        f"Top strengths: <b>{best_txt}</b>",
        f"Top opportunities: <b>{worst_txt}</b>",
        "This report is generated using automated signals to guide prioritization and remediation.",
    ]
    bullets = Paragraph("<br/>".join([f"• {s}" for s in summary]), styles["Body"])

    right_col = KeepTogether([
        badge,
        Spacer(1, 4*mm),
        Table([[chips[0], chips[1], chips[2]]], colWidths=[52*mm, 52*mm, 52*mm]),
        Spacer(1, 4*mm),
        bullets
    ])

    layout = Table([[donut_img, Spacer(1, 1), right_col]], colWidths=[78*mm, 6*mm, 86*mm])
    layout.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elems.append(layout)

    elems.append(Spacer(1, 8*mm))

    note = (
        "Scope: The scanner evaluates SEO signals, performance footprint, security headers, link structure, "
        "AI-readiness indicators, and competitive benchmarks (where available). "
        "For regulated industries or critical risk posture, a manual security assessment is recommended."
    )
    elems.append(_card("Scope & Disclaimer", [Paragraph(note, styles["Muted"])], styles, accent_color=BRAND["primary"]))

    return elems


# =========================================================
# Page 2: Executive Summary + visuals + risk + quick wins
# =========================================================
def _page2_exec_summary(meta: PdfMeta, overall_score: float, grade: str,
                        bar_png: bytes, radar_png: bytes, styles,
                        scores: Dict[str, float], breakdown: Dict[str, Dict[str, Any]]):
    elems: List[Any] = []

    elems.append(Paragraph("Executive Summary", styles["H1"]))
    elems.append(Paragraph(
        f"This summary highlights key outcomes for <b>{meta.audited_url}</b>. "
        f"Overall score: <b>{int(round(overall_score))}</b> (Grade <b>{grade}</b>).",
        styles["Body"]
    ))
    elems.append(Spacer(1, 5*mm))

    # Charts
    img_bar = Image(io.BytesIO(bar_png), width=165*mm, height=62*mm)
    img_radar = Image(io.BytesIO(radar_png), width=165*mm, height=85*mm)
    img_bar.hAlign = "CENTER"
    img_radar.hAlign = "CENTER"

    elems.append(_card("Score Visualizations", [img_bar, Spacer(1, 2*mm), img_radar], styles))

    elems.append(Spacer(1, 5*mm))

    # Category table
    rows = [["Category", "Score", "Risk", "Interpretation"]]
    order = [
        ("seo", "SEO"),
        ("performance", "Performance"),
        ("security", "Security"),
        ("links", "Links"),
        ("ai", "AI Readiness"),
        ("competitors", "Competitors"),
    ]
    for key, label in order:
        sc = float(scores.get(key, 0))
        risk = _risk_level(sc)
        rows.append([label, f"{int(round(sc))}", risk, _score_to_label(sc)])

    t = Table(rows, colWidths=[40*mm, 22*mm, 25*mm, 83*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND["primary"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (1, 1), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, BRAND["border"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND["bg_soft"]]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    for i in range(1, len(rows)):
        rc = _risk_color(rows[i][2])
        t.setStyle(TableStyle([
            ("TEXTCOLOR", (2, i), (2, i), rc),
            ("FONTNAME", (2, i), (2, i), "Helvetica-Bold"),
        ]))

    top_risks = _derive_top_risks(scores)
    quick_wins = _derive_quick_wins(breakdown, scores)

    elems.append(_card("Category Summary & Risk View", [
        t,
        Spacer(1, 4*mm),
        Paragraph("<b>Top Risks (prioritize):</b>", styles["Body"]),
        _bullets(top_risks, styles, CAPS["max_top_risks"]),
        Spacer(1, 3*mm),
        Paragraph("<b>Quick Wins (low effort / high impact):</b>", styles["Body"]),
        _bullets(quick_wins, styles, CAPS["max_quick_wins"]),
    ], styles, accent_color=BRAND["info"]))

    return elems


# =========================================================
# Page 3: SEO Deep Dive (international audit style)
# =========================================================
def _page3_seo_deep_dive(meta: PdfMeta, breakdown: Dict[str, Dict[str, Any]], styles, scores: Dict[str, float]):
    elems: List[Any] = []

    seo = breakdown.get("seo") or {}
    seo_score = _clamp_score(_num(seo.get("score"), 0))
    extras = seo.get("extras") or {}

    elems.append(Paragraph("Technical Deep Dive — SEO", styles["H1"]))
    elems.append(Paragraph(
        f"SEO score: <b>{int(round(seo_score))}</b> ({_score_to_label(seo_score)}). "
        "This section focuses on discoverability signals and indexing readiness.",
        styles["Body"]
    ))
    elems.append(Spacer(1, 4*mm))

    findings = _top_findings_from_extras(extras, max_items=CAPS["max_extras_findings"])

    # Best-practice guidance (safe, universal)
    recommendations = [
        "Ensure unique titles and meta descriptions for primary pages; avoid duplicates and truncation.",
        "Validate canonical URLs and avoid conflicting indexing directives (robots meta vs headers).",
        "Add structured data (Schema.org) where relevant (Organization, Product, Article, FAQ).",
        "Use clear heading hierarchy (H1/H2/H3) aligned to search intent.",
        "Strengthen internal linking to key conversion pages using descriptive anchor text.",
        "Ensure OpenGraph/Twitter metadata for consistent sharing previews.",
    ]

    elems.append(_card("Observed SEO Signals (from scanner)", [
        Paragraph("Key signals extracted during scan:", styles["Body"]),
        Spacer(1, 2*mm),
        _bullets(findings, styles, CAPS["max_extras_findings"]),
    ], styles, accent_color=BRAND["warning"]))

    elems.append(Spacer(1, 4*mm))
    elems.append(_card("Recommendations (Industry Best Practice)", [
        _bullets(recommendations, styles, CAPS["max_exec_bullets"]),
        Paragraph(
            "Note: Recommendations are prioritized based on typical impact; adjust to your business goals and site type.",
            styles["Muted"]
        ),
    ], styles, accent_color=BRAND["primary"]))

    return elems


# =========================================================
# Page 4: Performance + Security Deep Dive
# =========================================================
def _page4_perf_security(meta: PdfMeta, breakdown: Dict[str, Dict[str, Any]], styles, scores: Dict[str, float]):
    elems: List[Any] = []

    perf = breakdown.get("performance") or {}
    sec = breakdown.get("security") or {}

    perf_score = _clamp_score(_num(perf.get("score"), 0))
    sec_score = _clamp_score(_num(sec.get("score"), 0))

    perf_extras = perf.get("extras") or {}

    elems.append(Paragraph("Technical Deep Dive — Performance & Security", styles["H1"]))
    elems.append(Paragraph(
        f"Performance score: <b>{int(round(perf_score))}</b> • "
        f"Security score: <b>{int(round(sec_score))}</b>.",
        styles["Body"]
    ))
    elems.append(Spacer(1, 4*mm))

    perf_findings = _top_findings_from_extras(perf_extras, max_items=CAPS["max_extras_findings"])

    perf_actions = [
        "Compress and properly size images; prefer modern formats (WebP/AVIF) where supported.",
        "Minify CSS/JS and defer non-critical scripts; reduce render-blocking resources.",
        "Enable caching headers (Cache-Control) and compression (gzip/brotli) for text assets.",
        "Use CDN for static assets and optimize server response time (TTFB).",
    ]

    # Security table (defensive)
    sec_rows = [["Signal", "Value"]]
    sec_rows.append(["HTTPS", "Yes" if bool(sec.get("https")) else "No"])
    sec_rows.append(["HSTS", "Yes" if bool(sec.get("hsts")) else "No"])
    sec_rows.append(["HTTP Status", _safe(sec.get("status_code"))])
    sec_rows.append(["Server", _safe(sec.get("server"))])

    sec_tbl = Table(sec_rows, colWidths=[55*mm, 110*mm])
    sec_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND["primary"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, BRAND["border"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND["bg_soft"]]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    sec_actions = [
        "Enforce HTTPS site-wide and redirect HTTP -> HTTPS.",
        "Enable HSTS after confirming HTTPS stability (avoid locking out subdomains inadvertently).",
        "Add/verify core security headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy).",
        "Review cookies for Secure/HttpOnly/SameSite on authenticated sessions.",
    ]

    elems.append(_card("Performance Signals (from scanner)", [
        Paragraph(f"Key performance signals extracted during scan:", styles["Body"]),
        Spacer(1, 2*mm),
        _bullets(perf_findings, styles, CAPS["max_extras_findings"]),
        Spacer(1, 3*mm),
        Paragraph("<b>Performance Actions (Priority):</b>", styles["Body"]),
        _bullets(perf_actions, styles, CAPS["max_exec_bullets"]),
    ], styles, accent_color=BRAND["info"]))

    elems.append(Spacer(1, 4*mm))
    elems.append(_card("Security Posture (Transport & Headers)", [
        sec_tbl,
        Spacer(1, 3*mm),
        Paragraph("<b>Security Actions (Priority):</b>", styles["Body"]),
        _bullets(sec_actions, styles, CAPS["max_exec_bullets"]),
    ], styles, accent_color=BRAND["danger"]))

    return elems


# =========================================================
# Page 5: Links + AI + Competitors + Roadmap + Appendix
# =========================================================
def _page5_links_ai_action_appendix(meta: PdfMeta, result: Dict[str, Any],
                                   breakdown: Dict[str, Dict[str, Any]], styles,
                                   scores: Dict[str, float]):
    elems: List[Any] = []

    links = breakdown.get("links") or {}
    ai = breakdown.get("ai") or {}
    comp = breakdown.get("competitors") or {}

    elems.append(Paragraph("Links, AI Readiness & Action Plan", styles["H1"]))
    elems.append(Paragraph(
        "This section consolidates link footprint, AI-readiness, competitive benchmarks, and a prioritized roadmap.",
        styles["Body"]
    ))
    elems.append(Spacer(1, 4*mm))

    # Links summary
    internal = links.get("internal_links_count", 0)
    external = links.get("external_links_count", 0)
    total = links.get("total_links_count", 0)

    links_summary = Paragraph(
        f"<b>Links:</b> Internal {_safe(internal)} • External {_safe(external)} • Total {_safe(total)} • "
        f"Score <b>{int(round(scores.get('links', 0)))}</b>",
        styles["Body"]
    )

    # AI / competitor summary
    top_comp = comp.get("top_competitor_score")
    comp_line = f"Top competitor score: {_safe(top_comp)}" if top_comp is not None else "Top competitor score: —"
    ai_line = f"AI readiness score: <b>{int(round(scores.get('ai', 0)))}</b>"
    comp_score_line = f"Competitors score: <b>{int(round(scores.get('competitors', 0)))}</b>"

    # Roadmap (international standard)
    roadmap = [
        "P0 (0–72 hours): Fix critical security gaps (HTTPS/HSTS), broken redirects, and missing core metadata.",
        "P1 (1–2 weeks): Reduce page weight, remove render-blocking assets, compress images, and enable caching.",
        "P2 (2–4 weeks): Improve structured data, content hierarchy, and internal linking to key conversion pages.",
        "P3 (ongoing): Establish monitoring, competitor benchmarking, and content/UX iteration cycles.",
    ]

    # Dynamic cards (if present)
    dyn = result.get("dynamic") or {}
    cards = dyn.get("cards") or []
    cards = cards[:CAPS["max_dynamic_cards"]] if isinstance(cards, list) else []

    cards_flow: List[Any] = []
    if cards:
        cards_flow.append(Paragraph("<b>Highlights (from engine):</b>", styles["Body"]))
        bullets = []
        for c in cards:
            title = _safe(c.get("title"))
            body = _safe(c.get("body"))
            bullets.append(f"{title}: {body}")
        cards_flow.append(_bullets(bullets, styles, CAPS["max_dynamic_cards"]))
    else:
        cards_flow.append(Paragraph("No additional highlight cards returned for this run.", styles["Muted"]))

    # KV appendix (capped)
    kv = dyn.get("kv") or []
    kv_tbl = None
    if isinstance(kv, list) and kv:
        rows = [["Key", "Value"]]
        for item in kv[:CAPS["max_kv_rows"]]:
            rows.append([_safe(item.get("key")), _safe(item.get("value"))])

        kv_tbl = Table(rows, colWidths=[55*mm, 110*mm])
        kv_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND["primary"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, BRAND["border"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND["bg_soft"]]),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

    # Raw JSON short appendix (optional)
    raw_json = ""
    try:
        import json
