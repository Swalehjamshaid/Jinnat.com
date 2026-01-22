import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend


class ScoreBar(Flowable):
    """Simple horizontal score bar widget"""
    def __init__(self, score, width=380, height=18, max_score=100, label=None):
        Flowable.__init__(self)
        self.score = min(max(score, 0), max_score)
        self.width = width
        self.height = height
        self.max_score = max_score
        self.label = label or f"{int(self.score)}%"

    def wrap(self, *args):
        return (self.width, self.height + 10 if self.label else self.height)

    def draw(self):
        self.canv.saveState()
        # Background
        self.canv.setFillColor(colors.lightgrey)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        
        # Filled
        fill_width = (self.score / self.max_score) * self.width
        color = colors.green if self.score >= 80 else colors.orange if self.score >= 60 else colors.red
        self.canv.setFillColor(color)
        self.canv.rect(0, 0, fill_width, self.height, fill=1, stroke=0)
        
        # Border
        self.canv.setStrokeColor(colors.black)
        self.canv.rect(0, 0, self.width, self.height, fill=0, stroke=1)
        
        # Label
        self.canv.setFont("Helvetica-Bold", 10)
        text_color = colors.white if fill_width > 60 else colors.black
        self.canv.setFillColor(text_color)
        self.canv.drawCentredString(fill_width / 2 if fill_width > 60 else fill_width + 10, 4, self.label)
        
        self.canv.restoreState()


def generate_full_audit_pdf(data, out_path):
    """
    CATEGORY A - METRIC 10: Certified Export Readiness.
    Generates a professional ~5-7 page International Standard PDF report
    with comprehensive details, clean format, graphical presentations,
    and competitor analysis (assumes 'competitors' key in data as list of similar dicts).
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()

    # Custom styles for clean format
    title_style = ParagraphStyle('Title', alignment=1, fontSize=24, spaceAfter=12, textColor=colors.darkblue)
    h1 = ParagraphStyle('Heading1', parent=styles['Heading1'], fontSize=18, spaceAfter=10, textColor=colors.black)
    h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=14, spaceAfter=8)
    h3 = ParagraphStyle('Heading3', parent=styles['Heading3'], fontSize=12, spaceAfter=6)
    normal = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10, spaceAfter=4)
    summary = ParagraphStyle('Summary', parent=normal, textColor=colors.grey, spaceAfter=8)

    story = []

    # Helper to add header/footer (for all pages)
    def add_page_elements(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(20*mm, doc.bottomMargin - 5*mm, f"Certified Audit Report - {data.get('url', 'N/A')}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 5*mm, f"Page {doc.page}")
        canvas.restoreState()

    doc.onLaterPages = add_page_elements
    doc.onFirstPage = add_page_elements

    # ────────────────────────────────────────────────
    # Page 1 – Professional Cover
    # ────────────────────────────────────────────────
    story.append(Spacer(1, 50*mm))
    story.append(Paragraph("CERTIFIED WEBSITE AUDIT REPORT", title_style))
    story.append(Spacer(1, 10*mm))

    url = data.get('url', 'N/A')
    story.append(Paragraph(f"Website: {url}", h2))
    story.append(Spacer(1, 4*mm))

    overall = data.get('overall_score', 0)
    grade = data.get('grade', 'B')
    story.append(Paragraph(f"Global Health Score: {overall}%", h2))
    story.append(Paragraph(f"Final Grade: {grade}", h2))
    story.append(Spacer(1, 10*mm))

    story.append(ScoreBar(overall, width=400, height=24, label=f"{overall}% - Grade {grade}"))
    story.append(Spacer(1, 20*mm))

    story.append(Paragraph("Comprehensive Export Readiness Assessment", summary))
    story.append(Paragraph("Generated on: [Date Placeholder]", summary))  # Add dynamic date if needed
    story.append(PageBreak())

    # ────────────────────────────────────────────────
    # Page 2 – Executive Summary & Category Overview
    # ────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", h1))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(f"This report evaluates the website '{url}' across key categories for export readiness.", normal))
    story.append(Paragraph(f"Overall Performance: {overall}% ({grade}) - Strong in [Strengths Placeholder], opportunities in [Weaknesses Placeholder].", normal))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("Category Breakdown", h2))
    story.append(Spacer(1, 4*mm))

    categories = data.get('categories', {})
    cat_data = [["Category", "Score", "Grade"]]
    cat_scores = []
    cat_names = []

    for cat_name, info in categories.items():
        score = info.get('score', 0)
        cat_grade = 'A' if score >= 85 else 'B' if score >= 70 else 'C' if score >= 50 else 'D/F'
        cat_data.append([cat_name, f"{score}%", cat_grade])
        cat_scores.append(score)
        cat_names.append(cat_name)

    # Clean table style
    cat_table = Table(cat_data, colWidths=[240, 80, 80])
    cat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,1), (2,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ]))
    story.append(cat_table)
    story.append(Spacer(1, 8*mm))

    # Graphical: Pie Chart for Category Distribution
    if cat_scores:
        story.append(Paragraph("Category Score Distribution", h3))
        drawing = Drawing(400, 200)
        pie = Pie()
        pie.x = 100
        pie.y = 20
        pie.width = pie.height = 150
        pie.data = cat_scores
        pie.labels = cat_names
        pie.slices.strokeWidth = 0.5
        pie.slices.fontSize = 8

        legend = Legend()
        legend.x = 260
        legend.y = 100
        legend.dx = 8
        legend.dy = 8
        legend.fontName = 'Helvetica'
        legend.fontSize = 8
        legend.boxAnchor = 'w'
        legend.columnMaximum = 10
        legend.strokeWidth = 0.5
        legend.strokeColor = colors.grey
        legend.deltax = 75
        legend.deltay = 0
        legend.autoXPadding = 5
        legend.yGap = 0
        legend.dxTextSpace = 5
        legend.alignment = 'right'
        legend.columnMaximum = 99
        legend.rightPadding = 15
        legend.colorNamePairs = [(pie.slices[i].fillColor, (pie.labels[i][0:20], '%0.2f%%' % (pie.data[i]/sum(pie.data)*100.0))) for i in range(len(pie.data))]

        drawing.add(pie)
        drawing.add(legend)
        story.append(drawing)

    story.append(PageBreak())

    # ────────────────────────────────────────────────
    # Page 3 – Competitor Analysis (New Section)
    # ────────────────────────────────────────────────
    competitors = data.get('competitors', [])  # Assume list of dicts like main data
    if competitors:
        story.append(Paragraph("Competitor Analysis", h1))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("Comparison with key competitors to benchmark performance.", normal))
        story.append(Spacer(1, 8*mm))

        comp_data = [["Website", "Overall Score", "Grade"]]
        comp_scores = [overall]
        comp_names = [url.split('//')[-1] if url else 'Main']  # Short name

        for comp in competitors:
            c_url = comp.get('url', 'Competitor')
            c_score = comp.get('overall_score', 0)
            c_grade = comp.get('grade', 'B')
            comp_data.append([c_url, f"{c_score}%", c_grade])
            comp_scores.append(c_score)
            comp_names.append(c_url.split('//')[-1])

        # Comparison Table
        comp_table = Table(comp_data, colWidths=[240, 80, 80])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (1,1), (2,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 8*mm))

        # Graphical: Bar Chart for Comparison
        story.append(Paragraph("Score Comparison", h3))
        drawing = Drawing(400, 200)
        bc = HorizontalBarChart()
        bc.x = 50
        bc.y = 20
        bc.height = 150
        bc.width = 300
        bc.data = [comp_scores]
        bc.categoryAxis.categoryNames = comp_names
        bc.categoryAxis.labels.angle = 45
        bc.categoryAxis.labels.dy = -10
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars[0].fillColor = colors.blue
        bc.bars.strokeWidth = 0.5
        drawing.add(bc)
        story.append(drawing)
        story.append(Spacer(1, 8*mm))

        # Brief Insights
        story.append(Paragraph("Insights: Your site outperforms competitors in [Areas], but lags in [Others]. Recommendations: [Placeholder].", summary))

    else:
        story.append(Paragraph("Competitor Analysis", h1))
        story.append(Paragraph("No competitor data provided.", normal))

    story.append(PageBreak())

    # ────────────────────────────────────────────────
    # Pages 4+ – Detailed Category Breakdown (Comprehensive)
    # ────────────────────────────────────────────────
    for i, (cat_name, info) in enumerate(categories.items(), start=1):
        story.append(Paragraph(f"Category {i}: {cat_name}", h1))
        story.append(Spacer(1, 4*mm))

        score = info.get('score', 0)
        cat_grade = 'A' if score >= 85 else 'B' if score >= 70 else 'C' if score >= 50 else 'D/F'
        story.append(Paragraph(f"Health Score: {score}% ({cat_grade})", h2))
        story.append(Spacer(1, 4*mm))
        story.append(ScoreBar(score, width=400, height=20))
        story.append(Spacer(1, 8*mm))

        story.append(Paragraph("Description: [Category Description Placeholder]. Strengths: [ ]. Opportunities: [ ].", normal))
        story.append(Spacer(1, 8*mm))

        metrics = info.get('metrics', {})
        if metrics:
            story.append(Paragraph("Detailed Metrics", h3))
            t_data = [["Metric", "Value", "Status"]]
            for key, val in metrics.items():
                nice_key = key.replace('_', ' ').title()
                status = 'Good' if int(str(val).rstrip('%')) > 70 else 'Needs Improvement'  # Simple logic
                t_data.append([nice_key, str(val), status])

            t = Table(t_data, colWidths=[220, 100, 120])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.darkblue),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('ALIGN', (1,1), (2,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 6),
                ('FONTSIZE', (0,0), (-1,-1), 10),
            ]))
            story.append(t)

        # Add per-category competitor comparison if available
        if competitors:
            story.append(Spacer(1, 8*mm))
            story.append(Paragraph("Competitor Comparison for this Category", h3))
            comp_cat_data = [["Website", "Score"]]
            comp_cat_data.append(["Main Site", f"{score}%"])
            for comp in competitors:
                c_cat = comp.get('categories', {}).get(cat_name, {})
                c_score = c_cat.get('score', 0)
                comp_cat_data.append([comp.get('url', 'Comp'), f"{c_score}%"])

            comp_cat_table = Table(comp_cat_data, colWidths=[240, 200])
            comp_cat_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ]))
            story.append(comp_cat_table)

        story.append(PageBreak())

    # ────────────────────────────────────────────────
    # Final Page – Recommendations & Conclusion
    # ────────────────────────────────────────────────
    story.append(Paragraph("Recommendations & Conclusion", h1))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Based on the audit, prioritize improvements in low-scoring categories. Aim for 85%+ overall.", normal))
    story.append(Paragraph("Next Steps: [Actionable List Placeholder].", normal))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("For questions, contact [Support Placeholder].", summary))

    # Build
    doc.build(story)
    return out_path
