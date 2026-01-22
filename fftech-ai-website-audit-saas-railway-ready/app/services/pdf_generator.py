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


class ScoreBar(Flowable):
    """Custom horizontal score/progress bar"""
    def __init__(self, score, width=380, height=20, max_score=100):
        Flowable.__init__(self)
        self.score = min(max(float(score), 0), max_score)
        self.width = width
        self.height = height
        self.max_score = max_score

    def wrap(self, availWidth, availHeight):
        return (self.width, self.height + 4)

    def draw(self):
        self.canv.saveState()
        # Background (unfilled part)
        self.canv.setFillColor(colors.lightgrey)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        # Filled part
        fill_width = (self.score / self.max_score) * self.width
        if self.score >= 80:
            col = colors.ForestGreen
        elif self.score >= 60:
            col = colors.orange
        else:
            col = colors.red

        self.canv.setFillColor(col)
        self.canv.rect(0, 0, fill_width, self.height, fill=1, stroke=0)

        # Border
        self.canv.setStrokeColor(colors.black)
        self.canv.rect(0, 0, self.width, self.height, fill=0, stroke=1)

        # Text inside / beside
        self.canv.setFont("Helvetica-Bold", 10)
        text = f"{self.score:.0f}%"
        if fill_width > 50:
            self.canv.setFillColor(colors.white)
            self.canv.drawCentredString(fill_width / 2, 6, text)
        else:
            self.canv.setFillColor(colors.black)
            self.canv.drawString(fill_width + 8, 6, text)

        self.canv.restoreState()


def generate_full_audit_pdf(data, out_path):
    """
    CATEGORY A - METRIC 10: Certified Export Readiness.
    Generates a professional ~5-page graphical PDF report.
    Keeps same input/output signature.
    """
    # Ensure output directory exists
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=18*mm,
        bottomMargin=18*mm
    )

    styles = getSampleStyleSheet()

    # Custom styles for better look
    title_style = ParagraphStyle(
        name='CustomTitle',
        parent=styles['Title'],
        fontSize=22,
        alignment=1,
        spaceAfter=18,
        textColor=colors.darkblue
    )

    h1 = ParagraphStyle(
        name='Heading1',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=10
    )

    h2 = ParagraphStyle(
        name='Heading2',
        parent=styles['Heading2'],
        fontSize=13,
        spaceAfter=8
    )

    normal = styles['Normal']

    story = []

    # ────────────────────────────────────────────────
    # Page 1 – Cover
    # ────────────────────────────────────────────────
    story.append(Spacer(1, 70*mm))
    story.append(Paragraph("CERTIFIED WEBSITE AUDIT REPORT", title_style))
    story.append(Spacer(1, 18*mm))

    url = data.get('url', 'N/A')
    story.append(Paragraph(f"Website: {url}", h2))
    story.append(Spacer(1, 6*mm))

    overall_score = data.get('overall_score', 0)
    grade = data.get('grade', 'B')
    story.append(Paragraph(f"Global Health Score: {overall_score}%", h2))
    story.append(Paragraph(f"Final Grade: {grade}", h2))
    story.append(Spacer(1, 14*mm))

    story.append(ScoreBar(overall_score, width=400, height=24))
    story.append(Spacer(1, 30*mm))

    story.append(Paragraph("Professional Export Readiness Assessment Report", normal))
    story.append(PageBreak())

    # ────────────────────────────────────────────────
    # Page 2 – Category Overview + Chart
    # ────────────────────────────────────────────────
    story.append(Paragraph("Audit Summary", h1))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f"Website audited: {url}", normal))
    story.append(Spacer(1, 12*mm))

    categories = data.get('categories', {})

    # Summary table
    summary_data = [["Category", "Score", "Grade"]]
    cat_names = []
    cat_scores = []

    for cat, info in categories.items():
        score = info.get('score', 0)
        grade = 'A' if score >= 85 else 'B' if score >= 70 else 'C' if score >= 50 else 'D'
        summary_data.append([cat, f"{score}%", grade])
        cat_names.append(cat[:18])   # shorten for chart labels
        cat_scores.append(score)

    summary_table = Table(summary_data, colWidths=[240, 80, 80])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.6, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 7),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14*mm))

    # Horizontal bar chart of category scores
    if cat_scores:
        story.append(Paragraph("Category Performance Overview", h2))
        story.append(Spacer(1, 6*mm))

        drawing = Drawing(420, 160)
        bc = HorizontalBarChart()
        bc.x = 70
        bc.y = 20
        bc.height = 120
        bc.width = 330
        bc.data = [cat_scores]
        bc.categoryAxis.categoryNames = cat_names
        bc.categoryAxis.labels.boxAnchor = 'e'
        bc.categoryAxis.labels.dx = -5
        bc.categoryAxis.labels.dy = -2
        bc.categoryAxis.labels.angle = -30
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars.strokeWidth = 0.6
        bc.bars.fillColor = colors.mediumblue
        drawing.add(bc)
        story.append(drawing)

    story.append(PageBreak())

    # ────────────────────────────────────────────────
    # Pages 3–5+: Category Details
    # ────────────────────────────────────────────────
    for cat_name, info in categories.items():
        story.append(Paragraph(f"Category: {cat_name}", h1))
        story.append(Spacer(1, 6*mm))

        score = info.get('score', 0)
        story.append(Paragraph(f"Section Health Score: {score}%", h2))
        story.append(Spacer(1, 8*mm))
        story.append(ScoreBar(score, width=400, height=22))
        story.append(Spacer(1, 12*mm))

        metrics = info.get('metrics', {})
        if metrics:
            story.append(Paragraph("Metrics", h2))
            story.append(Spacer(1, 4*mm))

            table_data = [["Metric", "Value"]]
            for key, value in metrics.items():
                nice_key = key.replace('_', ' ').title()
                table_data.append([nice_key, str(value)])

            t = Table(table_data, colWidths=[320, 130])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.black),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ALIGN', (1,1), (1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 7),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(t)

        story.append(PageBreak())

    # Optional last page if needed (e.g. recommendations)
    # story.append(Paragraph("Recommendations & Next Steps", h1))
    # story.append(Spacer(1, 8*mm))
    # story.append(Paragraph("• Improve low-scoring categories\n• Re-audit in 3 months\n• ...", normal))
    # story.append(PageBreak())

    # Build PDF
    doc.build(story)
    return out_path
