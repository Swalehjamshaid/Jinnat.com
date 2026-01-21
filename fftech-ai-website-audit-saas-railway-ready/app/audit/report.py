import os
from datetime import datetime
from typing import Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.piecharts import Pie

from .utils import clamp  # assuming you have this
from ..config import settings

# ── Branding & Colors ───────────────────────────────────────────────────────
BRAND_NAME = settings.BRAND_NAME
LOGO_PATH = os.path.join('static', 'img', 'logo.png')  # relative to project root
PRIMARY_BLUE = colors.HexColor('#2563eb')
SECONDARY_SKY = colors.HexColor('#0ea5e9')
ACCENT_RED = colors.HexColor('#ef4444')
NEUTRAL_GRAY = colors.HexColor('#64748b')
BG_LIGHT = colors.HexColor('#f8fafc')

# ── Helper: Create Bar Chart ────────────────────────────────────────────────
def create_bar_chart(title: str, data: Dict[str, float], width=400, height=200):
    drawing = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x = 50
    bc.y = 50
    bc.height = 120
    bc.width = 300
    bc.data = [list(data.values())]
    bc.categoryNames = list(data.keys())
    bc.categoryAxis.categoryNames = list(data.keys())
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 100
    bc.valueAxis.valueStep = 20
    bc.bars.strokeWidth = 0.5
    bc.bars.fillColor = PRIMARY_BLUE
    bc.title = title
    drawing.add(bc)
    return drawing


# ── Helper: Create Pie Chart (for e.g. issue distribution) ───────────────────
def create_pie_chart(title: str, data: Dict[str, int], width=300, height=200):
    drawing = Drawing(width, height)
    pie = Pie()
    pie.x = 50
    pie.y = 50
    pie.width = 200
    pie.height = 200
    pie.data = list(data.values())
    pie.labels = list(data.keys())
    pie.slices.strokeWidth = 0.5
    # Color slices dynamically
    pie.slices[0].fillColor = SECONDARY_SKY
    pie.slices[1].fillColor = PRIMARY_BLUE
    pie.slices[2].fillColor = ACCENT_RED
    drawing.add(pie)
    return drawing


# ── Main PDF Builder ────────────────────────────────────────────────────────
def build_pdf(
    audit_id: int,
    url: str,
    overall_score: float,
    grade: str,
    category_scores: Dict[str, float],
    metrics: Dict[str, Any],
    summary: Dict[str, Any],  # from analyzer: {'executive_summary', 'strengths', 'weaknesses', 'priority_fixes'}
    out_dir: str = settings.REPORT_DIR
) -> str:
    """
    Generates a professional 5-page PDF audit report with branding, charts,
    and executive insights.
    """
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, f"FF_Tech_Audit_Report_{audit_id}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2.5*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='HeaderTitle', fontSize=24, textColor=PRIMARY_BLUE, spaceAfter=12))
    styles.add(ParagraphStyle(name='SectionHeader', fontSize=16, textColor=SECONDARY_SKY, spaceAfter=8))
    styles.add(ParagraphStyle(name='BodyText', fontSize=11, leading=14, spaceAfter=8))
    styles.add(ParagraphStyle(name='Conclusion', fontSize=10, textColor=NEUTRAL_GRAY, italic=True))

    story = []

    # ── Common Header Elements ───────────────────────────────────────────────
    def add_header(title: str):
        story.append(Paragraph(f"{BRAND_NAME} AI Website Audit Report", styles['HeaderTitle']))
        story.append(Paragraph(f"URL: {url} | Audit ID: {audit_id} | Date: {datetime.now().strftime('%Y-%m-%d')}", styles['BodyText']))
        story.append(Paragraph(f"Overall Grade: **{grade}** ({overall_score}%)", styles['SectionHeader']))
        story.append(Spacer(1, 0.5*cm))

    # ── PAGE 1: Executive Summary ────────────────────────────────────────────
    add_header("Executive Summary")
    story.append(Paragraph("Executive Overview", styles['SectionHeader']))
    story.append(Paragraph(summary.get('executive_summary', 'No AI summary available.'), styles['BodyText']))

    # Strengths & Weaknesses
    story.append(Paragraph("Key Strengths", styles['SectionHeader']))
    for s in summary.get('strengths', ['Strong crawlability', 'Good HTTPS adoption']):
        story.append(Paragraph(f"• {s}", styles['BodyText']))

    story.append(Paragraph("Critical Weaknesses", styles['SectionHeader']))
    for w in summary.get('weaknesses', ['Missing metadata', 'Broken links detected']):
        story.append(Paragraph(f"• {w}", styles['BodyText']))

    story.append(Paragraph("Top Priority Fixes", styles['SectionHeader']))
    for p in summary.get('priority_fixes', ['Fix 4xx errors', 'Add ALT tags']):
        story.append(Paragraph(f"• {p}", styles['BodyText']))

    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Conclusion: Immediate action on broken links and metadata will yield the highest ROI.", styles['Conclusion']))

    # ── PAGE 2: Category Performance Overview ────────────────────────────────
    story.append(Spacer(1, 2*cm))  # New page
    add_header("Category Performance Breakdown")
    story.append(Paragraph("Overall Category Scores", styles['SectionHeader']))

    # Bar Chart for category scores
    cat_chart = create_bar_chart("Category Scores (%)", category_scores)
    story.append(cat_chart)

    # Table for scores
    data = [["Category", "Score (%)"]]
    for cat, score in category_scores.items():
        data.append([cat.replace('_', ' ').title(), f"{score:.1f}"])
    table = Table(data, colWidths=[8*cm, 4*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_BLUE),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(table)

    story.append(Paragraph("Conclusion: Performance and crawlability are strong foundations. On-page SEO needs attention.", styles['Conclusion']))

    # ── PAGE 3: Crawlability & Technical Health ──────────────────────────────
    story.append(Spacer(1, 2*cm))
    add_header("Crawlability & Technical Health")
    story.append(Paragraph(f"Total Pages Crawled: {metrics.get('total_pages_crawled', 'N/A')}", styles['BodyText']))
    story.append(Paragraph(f"Broken Links (4xx/5xx): {metrics.get('total_broken_links', 0)}", styles['BodyText']))

    # HTTP Status Pie Chart
    status_data = {
        "Success (2xx)": metrics.get('status_2xx', 0),
        "Redirects (3xx)": metrics.get('status_3xx', 0),
        "Errors (4xx/5xx)": metrics.get('status_4xx', 0) + metrics.get('status_5xx', 0)
    }
    pie_chart = create_pie_chart("HTTP Status Distribution", status_data)
    story.append(pie_chart)

    story.append(Paragraph("Conclusion: High error rates can waste crawl budget. Prioritize fixing 4xx errors.", styles['Conclusion']))

    # ── PAGE 4: On-Page SEO & Content Quality ────────────────────────────────
    story.append(Spacer(1, 2*cm))
    add_header("On-Page SEO & Content Quality")
    issues = [
        f"Missing Titles: {metrics.get('missing_title', 0)}",
        f"Missing Meta Descriptions: {metrics.get('missing_meta_desc', 0)}",
        f"Missing H1 Tags: {metrics.get('missing_h1', 0)}",
        f"Images without ALT: {metrics.get('img_no_alt', 0)}",
        f"Thin Content Pages: {metrics.get('thin_content_pages', 0)}",
    ]
    for issue in issues:
        story.append(Paragraph(f"• {issue}", styles['BodyText']))

    story.append(Paragraph("Conclusion: Complete metadata and ALT text will improve click-through rates and accessibility.", styles['Conclusion']))

    # ── PAGE 5: Performance Vitals & Growth Roadmap ─────────────────────────
    story.append(Spacer(1, 2*cm))
    add_header("Performance & Growth Roadmap")
    cwv = metrics.get('core_web_vitals', {}).get('desktop', {})
    story.append(Paragraph(f"PageSpeed Score: {cwv.get('score', 'N/A')}/100", styles['BodyText']))
    story.append(Paragraph(f"Largest Contentful Paint: {cwv.get('lcp', 'N/A')} ms", styles['BodyText']))
    story.append(Paragraph(f"Cumulative Layout Shift: {cwv.get('cls', 'N/A')}", styles['BodyText']))

    # Roadmap
    story.append(Paragraph("Phase 1 (0-30 Days): Fix critical issues", styles['SectionHeader']))
    story.append(Paragraph("• Resolve broken links\n• Add missing meta tags\n• Optimize images", styles['BodyText']))

    story.append(Paragraph("Phase 2 (30-90 Days): Advanced Optimization", styles['SectionHeader']))
    story.append(Paragraph("• Implement structured data\n• Improve mobile performance\n• Set up monitoring", styles['BodyText']))

    story.append(Paragraph(f"Projected ROI: +{round(100 - overall_score, 1)}% traffic growth potential", styles['SectionHeader']))
    story.append(Paragraph("Conclusion: Implementing this roadmap can significantly boost rankings and conversions.", styles['Conclusion']))

    # ── Build PDF ───────────────────────────────────────────────────────────────
    doc.build(story)
    return pdf_path
