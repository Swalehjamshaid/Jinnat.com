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
from reportlab.graphics.shapes import Drawing, String, Rect
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.legends import Legend


class ScoreBar(Flowable):
    """Simple horizontal score bar widget"""
    def __init__(self, score, width=380, height=18, max_score=100):
        Flowable.__init__(self)
        self.score = min(max(score, 0), max_score)
        self.width = width
        self.height = height
        self.max_score = max_score

    def wrap(self, *args):
        return (self.width, self.height)

    def draw(self):
        self.canv.saveState()
        # Background (gray = remaining)
        self.canv.setFillColor(colors.lightgrey)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        
        # Filled portion
        fill_width = (self.score / self.max_score) * self.width
        if self.score >= 80:
            color = colors.green
        elif self.score >= 60:
            color = colors.orange
        else:
            color = colors.red
            
        self.canv.setFillColor(color)
        self.canv.rect(0, 0, fill_width, self.height, fill=1, stroke=0)
        
        # Border
        self.canv.setStrokeColor(colors.black)
        self.canv.rect(0, 0, self.width, self.height, fill=0, stroke=1)
        
        # Text
        self.canv.setFillColor(colors.black)
        self.canv.setFont("Helvetica-Bold", 10)
        text = f"{int(self.score)}%"
        text_x = fill_width / 2 if fill_width > 40 else fill_width + 8
        text_color = colors.white if fill_width > 40 else colors.black
        self.canv.setFillColor(text_color)
        self.canv.drawCentredString(text_x, 6, text)
        self.canv.restoreState()


def generate_full_audit_pdf(data, out_path):
    """
    CATEGORY A - METRIC 10: Certified Export Readiness.
    Generates a professional ~5-page International Standard PDF report
    with better visuals and layout.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    h1 = ParagraphStyle('Heading1', parent=styles['Heading1'], fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=14, spaceAfter=10)
    h3 = ParagraphStyle('Heading3', parent=styles['Heading3'], fontSize=12, spaceAfter=8)
    normal = styles['Normal']

    story = []

    # ────────────────────────────────────────────────
    # Page 1 – Cover
    # ────────────────────────────────────────────────
    story.append(Spacer(1, 60*mm))
    story.append(Paragraph(
        "<font size=28><b>CERTIFIED WEBSITE AUDIT REPORT</b></font>",
        ParagraphStyle('Title', alignment=1, fontSize=28, spaceAfter=24)
    ))
    story.append(Spacer(1, 10*mm))

    url = data.get('url', 'N/A')
    story.append(Paragraph(f"<b>Website:</b> {url}", h2))
    story.append(Spacer(1, 6*mm))

    overall = data.get('overall_score', 0)
    grade = data.get('grade', 'B')
    story.append(Paragraph(f"<b>Global Health Score:</b> {overall}%", h2))
    story.append(Paragraph(f"<b>Final Grade:</b> {grade}", h2))

    story.append(Spacer(1, 16*mm))
    story.append(ScoreBar(overall, width=380, height=24))
    story.append(Spacer(1, 10*mm))

    story.append(Paragraph(
        "Professional Export Readiness Assessment — 2025",
        ParagraphStyle('Normal', alignment=1, fontSize=10, textColor=colors.grey)
    ))

    story.append(PageBreak())

    # ────────────────────────────────────────────────
    # Page 2 – Overall Summary + Category Scores
    # ────────────────────────────────────────────────
    story.append(Paragraph("Audit Summary", h1))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(f"Website: {url}", h3))
    story.append(Spacer(1, 10*mm))

    # Category overview table
    cat_data = [["Category", "Score", "Grade"]]
    categories = data.get('categories', {})

    for cat_name, info in categories.items():
        score = info.get('score', 0)
        # Very simple grade mapping (customize as needed)
        cat_grade = 'A' if score >= 85 else 'B' if score >= 70 else 'C' if score >= 50 else 'D'
        cat_data.append([cat_name, f"{score}%", cat_grade])

    cat_table = Table(cat_data, colWidths=[240, 80, 80])
    cat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.8, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(cat_table)
    story.append(Spacer(1, 12*mm))

    story.append(Paragraph("Category Performance Overview", h2))
    story.append(Spacer(1, 4*mm))

    # Mini bar chart for all categories
    if categories:
        drawing = Drawing(400, 180)
        bc = HorizontalBarChart()
        bc.x = 80
        bc.y = 20
        bc.height = 140
        bc.width = 300
        bc.categoryAxis.categoryNames = list(categories.keys())
        bc.data = [[info.get('score', 0) for info in categories.values()]]
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars.strokeWidth = 0.5
        bc.bars.fillColor = colors.blue
        drawing.add(bc)
        story.append(drawing)

    story.append(PageBreak())

    # ────────────────────────────────────────────────
    # Pages 3–5 (or more) – Detailed Category Breakdown
    # ────────────────────────────────────────────────
    for i, (cat_name, info) in enumerate(categories.items(), start=3):
        story.append(Paragraph(f"Category {i}: {cat_name}", h1))
        story.append(Spacer(1, 4*mm))

        score = info.get('score', 0)
        story.append(Paragraph(f"Section Health Score: {score}%", h2))
        story.append(Spacer(1, 6*mm))
        story.append(ScoreBar(score))
        story.append(Spacer(1, 12*mm))

        metrics = info.get('metrics', {})
        if metrics:
            story.append(Paragraph("Detailed Metrics", h3))
            story.append(Spacer(1, 4*mm))

            t_data = [["Metric", "Value"]]
            for key, val in metrics.items():
                # Try to make key more readable
                nice_key = key.replace('_', ' ').title()
                t_data.append([nice_key, str(val)])

            t = Table(t_data, colWidths=[320, 130])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.darkblue),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ALIGN', (1,1), (1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 7),
            ]))
            story.append(t)

        story.append(Spacer(1, 12*mm))
        story.append(PageBreak())

    # Build the document
    doc.build(story)
    return out_path
