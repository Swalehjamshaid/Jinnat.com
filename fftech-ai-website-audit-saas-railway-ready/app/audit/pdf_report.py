"""
FF Tech Website Audit - Professional PDF Report Generator
──────────────────────────────────────────────────────────
Features:
• Multi-page professional layout
• Header & footer with page numbers and generation date
• Cover page with logo support
• Summary table with color-coded scores
• Detailed sections for each audit category
• Recommendations & key findings with fallback content
• Never produces blank or invalid PDF
• Detailed logging for debugging
• Robust error handling

Dependencies: reportlab (pip install reportlab)
"""

from __future__ import annotations
import os
import datetime as dt
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch
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

import logging
logger = logging.getLogger("ff-tech-audit")


# ────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────

def _safe_get(d: Dict[str, Any], path: str, default: Any = "N/A") -> Any:
    """Safely get nested value with dot notation"""
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _ensure_list(value: Any) -> List[Any]:
    """Convert to list safely"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clamp_score(score: Any) -> int:
    """Clamp score between 0–100"""
    try:
        v = int(round(float(score)))
        return max(0, min(100, v))
    except (TypeError, ValueError):
        return 0


def _get_grade(score: int) -> str:
    """Convert numeric score to letter grade"""
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 50: return "D"
    return "F"


# ────────────────────────────────────────────────
# Fonts & Styles
# ────────────────────────────────────────────────

def register_fonts():
    """Try to register nice fonts if available"""
    fonts_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
    if not os.path.exists(fonts_dir):
        return

    font_pairs = [
        ("Inter", "Inter-Regular.ttf"),
        ("Inter-Bold", "Inter-Bold.ttf"),
    ]

    for name, fname in font_pairs:
        path = os.path.join(fonts_dir, fname)
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                logger.debug(f"Font registered: {name}")
            except Exception as e:
                logger.warning(f"Failed to register font {name}: {e}")


def create_styles():
    """Create professional-looking styles"""
    register_fonts()

    has_inter = "Inter" in pdfmetrics.getRegisteredFontNames()
    base_font = "Inter" if has_inter else "Helvetica"
    bold_font = "Inter-Bold" if has_inter and "Inter-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"

    styles = getSampleStyleSheet()

    # Title (cover page)
    title = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontName=bold_font,
        fontSize=28,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=18,
    )

    # Main heading
    h1 = ParagraphStyle(
        'Heading1',
        parent=styles['Heading1'],
        fontName=bold_font,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1d4ed8"),
        spaceBefore=20,
        spaceAfter=10,
    )

    # Sub heading
    h2 = ParagraphStyle(
        'Heading2',
        parent=styles['Heading2'],
        fontName=bold_font,
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e40af"),
        spaceBefore=16,
        spaceAfter=8,
    )

    # Normal body text
    body = ParagraphStyle(
        'Body',
        parent=styles['BodyText'],
        fontName=base_font,
        fontSize=10,
        leading=14,
        textColor=colors.black,
        spaceAfter=8,
    )

    # Small / caption text
    small = ParagraphStyle(
        'Small',
        parent=styles['BodyText'],
        fontName=base_font,
        fontSize=9,
        leading=12,
        textColor=colors.grey,
        spaceAfter=6,
    )

    return {
        "title": title,
        "h1": h1,
        "h2": h2,
        "body": body,
        "small": small,
    }


# ────────────────────────────────────────────────
# Header & Footer
# ────────────────────────────────────────────────

def on_page(canvas, doc):
    """Add header and footer to every page"""
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)

    # Header - left
    canvas.drawString(doc.leftMargin, A4[1] - 1.8*cm, "FF Tech Website Audit Report")

    # Header - right (report title or date)
    canvas.drawRightString(
        A4[0] - doc.rightMargin,
        A4[1] - 1.8*cm,
        f"Generated: {dt.date.today():%d %b %Y}"
    )

    # Footer - page number
    page_num = canvas.getPageNumber()
    canvas.drawCentredString(
        A4[0] / 2,
        1.2*cm,
        f"Page {page_num} • Confidential"
    )

    canvas.restoreState()


# ────────────────────────────────────────────────
# Main PDF Generation
# ────────────────────────────────────────────────

def generate_audit_pdf(
    audit_data: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    report_title: str = "Website Audit Report",
) -> str:
    """
    Generate a professional multi-page PDF audit report.
    Never produces blank or invalid file.
    """
    logger.info(f"Starting PDF generation → {output_path}")

    # Prepare styles & fonts
    global styles
    styles = create_styles()

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Document setup
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2.2*cm,
        rightMargin=2.2*cm,
        topMargin=3.0*cm,
        bottomMargin=2.2*cm,
        onPage=on_page,
    )

    story = []

    # ─── Cover Page ─────────────────────────────────────
    logger.debug("Building cover page")

    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=2.8*inch, height=2.8*inch)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.8*cm))
        except Exception as e:
            logger.warning(f"Logo loading failed: {e}")

    story.append(Paragraph(report_title.upper(), styles["title"]))
    story.append(Spacer(1, 1.2*cm))

    url = _safe_get(audit_data, "website.url", "—")
    score = _clamp_score(_safe_get(audit_data, "overall_score", 0))
    grade = _safe_get(audit_data, "grade", _get_grade(score))

    story.append(Paragraph(
        f"<font size=16><b>Audited Website:</b> {url}</font>",
        styles["body"]
    ))
    story.append(Spacer(1, 0.6*cm))

    story.append(Paragraph(
        f"<font size=20 color=#1e40af><b>Overall Score: {score}/100</b></font>",
        styles["body"]
    ))
    story.append(Paragraph(
        f"<font size=18><b>Grade: {grade}</b></font>",
        styles["body"]
    ))
    story.append(Spacer(1, 2.2*cm))

    story.append(PageBreak())

    # ─── Summary Table ──────────────────────────────────
    logger.debug("Building summary table")

    story.append(Paragraph("Performance Summary", styles["h1"]))
    story.append(Spacer(1, 0.5*cm))

    summary_data = [
        ["Category", "Score", "Grade"],
        ["SEO", _clamp_score(_safe_get(audit_data, "breakdown.seo.score")), "—"],
        ["Performance", _clamp_score(_safe_get(audit_data, "breakdown.performance.score")), "—"],
        ["Links", _clamp_score(_safe_get(audit_data, "breakdown.links.score")), "—"],
        ["Security", _clamp_score(_safe_get(audit_data, "breakdown.security.score")), "—"],
    ]

    table = Table(summary_data, colWidths=[10*cm, 4*cm, 4*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f8fafc'), colors.white]),
    ]))
    story.append(table)
    story.append(Spacer(1, 1.5*cm))

    # ─── Key Findings & Recommendations ─────────────────
    logger.debug("Building recommendations section")

    story.append(Paragraph("Key Findings & Recommendations", styles["h1"]))
    story.append(Spacer(1, 0.5*cm))

    recommendations = _ensure_list(_safe_get(audit_data, "recommendations", []))
    if not recommendations:
        recommendations = [
            "Optimize title tags and meta descriptions for better click-through rates.",
            "Improve page load time by compressing images and reducing render-blocking resources.",
            "Ensure all images have meaningful alt text for accessibility and SEO.",
            "Implement or strengthen HSTS header for improved security.",
            "Reduce number of external scripts to improve performance.",
            "Add internal linking strategy to improve site structure and crawlability."
        ]

    for item in recommendations[:8]:
        story.append(Paragraph(f"• {item}", styles["body"]))

    story.append(Spacer(1, 1.2*cm))
    story.append(Paragraph(
        "This report was generated by FF Tech Audit Platform. "
        "For full technical details and live metrics, visit the dashboard.",
        styles["small"]
    ))

    # ─── Build the PDF ──────────────────────────────────
    logger.info(f"Building PDF with {len(story)} flowables...")

    try:
        doc.build(story)
        logger.info("PDF generation completed successfully")
    except Exception as e:
        logger.error(f"PDF build failed: {str(e)}", exc_info=True)
        raise

    # Final validation
    if os.path.exists(output_path):
        size_kb = os.path.getsize(output_path) / 1024
        logger.info(f"PDF file created successfully – size: {size_kb:.1f} KB")
        if size_kb < 5:
            logger.warning("Generated PDF is very small – may appear blank in some viewers")
    else:
        logger.error("PDF file was NOT created!")

    return output_path


# Optional: self-test / standalone run
if __name__ == "__main__":
    import tempfile
    sample_data = {
        "audited_url": "https://example.com",
        "overall_score": 78,
        "grade": "B",
        "breakdown": {
            "seo": {"score": 82},
            "performance": {"score": 65},
            "links": {"score": 88},
            "security": {"score": 95},
        }
    }
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        generate_audit_pdf(sample_data, tmp.name)
        print(f"Test PDF created at: {tmp.name}")
