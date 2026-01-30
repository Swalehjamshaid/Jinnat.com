# app/audit/pdf_report.py
"""
PDF Website Audit Report Generator (5+ pages)

Dependencies:
  - reportlab

Install:
  pip install reportlab

Usage:
  from app.audit.pdf_report import generate_audit_pdf

  audit_data = {...}  # see sample at bottom
  generate_audit_pdf(audit_data, output_path="output/audit_report.pdf", logo_path="assets/logo.png")
"""

from __future__ import annotations

import os
import datetime as _dt
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
    KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# -----------------------------
# Helpers
# -----------------------------

def _safe_get(d: Dict[str, Any], path: str, default: Any = "N/A") -> Any:
    """
    Safely read nested dict keys using dot path:
      _safe_get(data, "audit.overall_score")
    """
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _ensure_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _fmt_date(value: Any) -> str:
    if value in (None, "", "N/A"):
        return _dt.date.today().strftime("%d %b %Y")
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.strftime("%d %b %Y")
    # accept ISO-like strings
    try:
        return _dt.datetime.fromisoformat(str(value)).strftime("%d %b %Y")
    except Exception:
        return str(value)


def _clamp_score(x: Any) -> Optional[int]:
    try:
        v = int(round(float(x)))
        return max(0, min(100, v))
    except Exception:
        return None


def _score_color(score: Optional[int]) -> colors.Color:
    # green >= 80, amber 60-79, red < 60, gray if missing
    if score is None:
        return colors.HexColor("#9CA3AF")
    if score >= 80:
        return colors.HexColor("#16A34A")
    if score >= 60:
        return colors.HexColor("#F59E0B")
    return colors.HexColor("#DC2626")


def _grade_from_score(score: Optional[int]) -> str:
    if score is None:
        return "N/A"
    if score >= 95:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "D"


# -----------------------------
# Styling / Layout
# -----------------------------

def _register_optional_fonts():
    """
    Optional: register custom fonts if you ship them with your repo.
    Keep safe: if not present, it won't crash.
    """
    # Example path if you add fonts later:
    # fonts_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
    fonts_dir = os.path.join(os.path.dirname(__file__), "assets", "fonts")
    candidates = [
        ("Inter", os.path.join(fonts_dir, "Inter-Regular.ttf")),
        ("InterBold", os.path.join(fonts_dir, "Inter-Bold.ttf")),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass


def _build_styles():
    styles = getSampleStyleSheet()

    # Base font fallback (Inter if registered, else Helvetica)
    base_font = "Inter" if "Inter" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    base_bold = "InterBold" if "InterBold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"

    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName=base_bold,
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=16,
    )
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontName=base_font,
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#334155"),
        spaceAfter=18,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName=base_bold,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName=base_bold,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=8,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName=base_font,
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#111827"),
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    small = ParagraphStyle(
        "Small",
        parent=styles["BodyText"],
        fontName=base_font,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
    )
    bullet = ParagraphStyle(
        "Bullet",
        parent=body,
        leftIndent=14,
        bulletIndent=6,
        spaceAfter=3,
    )

    return {
        "title": title,
        "subtitle": subtitle,
        "h1": h1,
        "h2": h2,
        "body": body,
        "small": small,
        "bullet": bullet,
        "base_font": base_font,
        "base_bold": base_bold,
    }


def _header_footer(canvas, doc, report_title="Website Audit Report"):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#64748B"))
    # Header
    canvas.drawString(doc.leftMargin, A4[1] - 0.75 * cm, report_title)
    # Footer: page number
    page_num = canvas.getPageNumber()
    canvas.drawRightString(A4[0] - doc.rightMargin, 0.75 * cm, f"Page {page_num}")
    canvas.restoreState()


# -----------------------------
# Components
# -----------------------------

def _kv_table(rows: List[List[str]]) -> Table:
    """
    Key/Value table for cover page metadata.
    """
    t = Table(rows, colWidths=[4.2 * cm, 11.8 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, colors.HexColor("#FFFFFF")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _score_dashboard_table(scores: Dict[str, Any]) -> Table:
    """
    Dashboard: category scores + color chips.
    """
    labels = [
        ("SEO score", "seo"),
        ("Performance score", "performance"),
        ("UX/UI score", "ux_ui"),
        ("Accessibility score", "accessibility"),
        ("Security score", "security"),
        ("Content quality score", "content_quality"),
    ]

    data = [["Category", "Score", "Grade"]]
    for label, key in labels:
        s = _clamp_score(scores.get(key))
        grade = _grade_from_score(s)
        data.append([label, "N/A" if s is None else str(s), grade])

    t = Table(data, colWidths=[9.0 * cm, 3.0 * cm, 4.0 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10.5),
        ("ALIGN", (1, 1), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]

    # Color the score cells based on value
    for row_idx in range(1, len(data)):
        score_text = data[row_idx][1]
        s = None if score_text == "N/A" else int(score_text)
        style.append(("TEXTCOLOR", (1, row_idx), (1, row_idx), _score_color(s)))

    t.setStyle(TableStyle(style))
    return t


def _bullets(story, items: List[str], styles):
    if not items:
        story.append(Paragraph("• No findings provided.", styles["body"]))
        return
    for it in items:
        story.append(Paragraph(f"• {it}", styles["body"]))


def _section(story, title: str, styles, intro: Optional[str] = None):
    story.append(Paragraph(title, styles["h1"]))
    if intro:
        story.append(Paragraph(intro, styles["body"]))
    story.append(Spacer(1, 6))


# -----------------------------
# Main Generator
# -----------------------------

def generate_audit_pdf(
    audit_data: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    report_title: str = "Website Audit Report",
) -> str:
    """
    Generate a multi-page PDF audit report.
    Returns output_path.

    audit_data: dict structure (flexible). Missing fields are handled.
    logo_path: optional path to a logo image (png/jpg)
    """

    _register_optional_fonts()
    styles = _build_styles()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=2.0 * cm,
        bottomMargin=1.7 * cm,
        title=report_title,
        author=_safe_get(audit_data, "brand.name", "Audit System"),
    )

    story = []

    # -----------------------------
    # Cover Page
    # -----------------------------
    website_name = _safe_get(audit_data, "website.name", "Website")
    website_url = _safe_get(audit_data, "website.url", "N/A")
    client_name = _safe_get(audit_data, "client.name", "N/A")
    audit_date = _fmt_date(_safe_get(audit_data, "audit.date", None))
    brand_name = _safe_get(audit_data, "brand.name", "Your Brand")

    story.append(Spacer(1, 18))

    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            img.drawHeight = 1.0 * inch
            img.drawWidth = 1.0 * inch
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 10))
        except Exception:
            # Ignore logo errors gracefully
            pass

    story.append(Paragraph(report_title, styles["title"]))
    story.append(Paragraph(f"<b>{website_name}</b><br/>{website_url}", styles["subtitle"]))

    cover_rows = [
        ["Client name", str(client_name)],
        ["Audit date", str(audit_date)],
        ["Brand", str(brand_name)],
    ]
    story.append(_kv_table(cover_rows))
    story.append(Spacer(1, 18))

    # Executive highlights on cover
    overall_score = _clamp_score(_safe_get(audit_data, "audit.overall_score", None))
    overall_grade = _safe_get(audit_data, "audit.grade", _grade_from_score(overall_score))
    verdict = _safe_get(audit_data, "audit.verdict", "N/A")

    story.append(Paragraph("Executive Summary (Snapshot)", styles["h2"]))
    snapshot = [
        ["Overall website score (0–100)", "N/A" if overall_score is None else str(overall_score)],
        ["Website grade (A+, A, B, C)", str(overall_grade)],
        ["Business health verdict", str(verdict)],
    ]
    story.append(_kv_table(snapshot))

    story.append(PageBreak())

    # -----------------------------
    # Page: Executive Summary
    # -----------------------------
    _section(story, "Executive Summary", styles)
    story.append(Paragraph(
        _safe_get(
            audit_data,
            "audit.executive_summary",
            "This report summarizes the website’s current health across SEO, performance, UX/UI, accessibility, security, and content quality.",
        ),
        styles["body"],
    ))

    story.append(Paragraph("Key risks & opportunities", styles["h2"]))
    risks = _ensure_list(_safe_get(audit_data, "audit.key_risks", []))
    opps = _ensure_list(_safe_get(audit_data, "audit.opportunities", []))

    story.append(Paragraph("<b>Key risks</b>", styles["body"]))
    _bullets(story, [str(x) for x in risks], styles)

    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Opportunities</b>", styles["body"]))
    _bullets(story, [str(x) for x in opps], styles)

    story.append(PageBreak())

    # -----------------------------
    # Page: Scope & Overview
    # -----------------------------
    _section(story, "Audit Scope & Objectives", styles)
    story.append(Paragraph("<b>What was audited</b>", styles["h2"]))
    _bullets(story, [str(x) for x in _ensure_list(_safe_get(audit_data, "scope.what", []))], styles)

    story.append(Paragraph("<b>Why it matters to the business</b>", styles["h2"]))
    story.append(Paragraph(str(_safe_get(audit_data, "scope.why", "N/A")), styles["body"]))

    story.append(Paragraph("<b>Tools & methodology used</b>", styles["h2"]))
    _bullets(story, [str(x) for x in _ensure_list(_safe_get(audit_data, "scope.tools", []))], styles)

    story.append(Spacer(1, 12))

    _section(story, "Website Overview", styles)
    story.append(Paragraph(f"<b>Industry & niche:</b> {_safe_get(audit_data, 'website.industry', 'N/A')}", styles["body"]))
    story.append(Paragraph(f"<b>Target audience:</b> {_safe_get(audit_data, 'website.audience', 'N/A')}", styles["body"]))

    goals = _ensure_list(_safe_get(audit_data, "website.goals", []))
    story.append(Paragraph("<b>Business goals (sales, leads, traffic)</b>", styles["h2"]))
    _bullets(story, [str(x) for x in goals], styles)

    story.append(PageBreak())

    # -----------------------------
    # Page: Score Dashboard
    # -----------------------------
    _section(story, "Overall Score Dashboard", styles)
    scores = _safe_get(audit_data, "scores", {})
    if not isinstance(scores, dict):
        scores = {}
    story.append(_score_dashboard_table(scores))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Interpretation: scores closer to 100 indicate stronger health. Prioritize categories with lower scores to improve business outcomes.",
        styles["small"],
    ))

    story.append(PageBreak())

    # -----------------------------
    # SEO Audit
    # -----------------------------
    _section(story, "SEO Audit (Search Visibility)", styles)

    story.append(Paragraph("<b>On-page SEO issues</b>", styles["h2"]))
    _bullets(story, [str(x) for x in _ensure_list(_safe_get(audit_data, "seo.on_page_issues", []))], styles)

    story.append(Paragraph("<b>Technical SEO issues</b>", styles["h2"]))
    _bullets(story, [str(x) for x in _ensure_list(_safe_get(audit_data, "seo.technical_issues", []))], styles)

    story.append(Paragraph("<b>Content gaps</b>", styles["h2"]))
    _bullets(story, [str(x) for x in _ensure_list(_safe_get(audit_data, "seo.content_gaps", []))], styles)

    story.append(Paragraph("<b>Keyword optimization level</b>", styles["h2"]))
    story.append(Paragraph(str(_safe_get(audit_data, "seo.keyword_optimization_level", "N/A")), styles["body"]))

    story.append(PageBreak())

    # -----------------------------
    # Performance & Speed
    # -----------------------------
    _section(story, "Performance & Speed Analysis", styles)

    story.append(Paragraph("<b>Core Web Vitals (LCP, CLS, INP/FID)</b>", styles["h2"]))
    cwv = _safe_get(audit_data, "performance.core_web_vitals", {})
    if not isinstance(cwv, dict):
        cwv = {}
    cwv_rows = [
        ["Metric", "Value", "Notes"],
        ["LCP", str(cwv.get("lcp", "N/A")), str(cwv.get("lcp_notes", ""))],
        ["CLS", str(cwv.get("cls", "N/A")), str(cwv.get("cls_notes", ""))],
        ["INP/FID", str(cwv.get("inp", cwv.get("fid", "N/A"))), str(cwv.get("inp_notes", cwv.get("fid_notes", "")))],
    ]
    t = Table(cwv_rows, colWidths=[3.5 * cm, 3.5 * cm, 9.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Mobile vs desktop speed</b>", styles["h2"]))
    story.append(Paragraph(str(_safe_get(audit_data, "performance.mobile_vs_desktop", "N/A")), styles["body"]))

    story.append(Paragraph("<b>Page size & load time issues</b>", styles["h2"]))
    _bullets(story, [str(x) for x in _ensure_list(_safe_get(audit_data, "performance.page_size_issues", []))], styles)

    story.append(PageBreak())

    # -----------------------------
    # Mobile Friendliness
    # -----------------------------
    _section(story, "Mobile Friendliness", styles)
    story.append(Paragraph("<b>Responsive design issues</b>", styles["h2"]))
    _bullets(story, [str(x) for x in _ensure_list(_safe_get(audit_data, "mobile.responsive_issues", []))], styles)

    story.append(Paragraph("<b>Mobile usability problems</b>", styles["h2"]))
    _bullets(story, [str(x) for x in _ensure_list(_safe_get(audit_data,
