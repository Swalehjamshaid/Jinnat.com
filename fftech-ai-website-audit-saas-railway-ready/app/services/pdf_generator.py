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
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import HorizontalBarChart


class ScoreBar(Flowable):
    """Clean horizontal score bar"""
    def __init__(self, score, width=380, height=18, max_score=100):
        Flowable.__init__(self)
        self.score = min(max(float(score or 0), 0), max_score)
        self.width = width
        self.height = height
        self.max_score = max_score

    def wrap(self, *args):
        return self.width, self.height + 6

    def draw(self):
        self.canv.saveState()
        # background
        self.canv.setFillColor(colors.lightgrey)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        # filled
        fillw = (self.score / self.max_score) * self.width
        col = colors.green if self.score >= 80 else colors.orange if self.score >= 60 else colors.red
        self.canv.setFillColor(col)
        self.canv.rect(0, 0, fillw, self.height, fill=1, stroke=0)

        # border
        self.canv.setStrokeColor(colors.black)
        self.canv.rect(0, 0, self.width, self.height, fill=0, stroke=1)

        # text
        self.canv.setFont("Helvetica-Bold", 10)
        txt = f"{int(self.score)}%"
        if fillw > 50:
            self.canv.setFillColor(colors.white)
            self.canv.drawCentredString(fillw / 2, 5, txt)
        else:
            self.canv.setFillColor(colors.black)
            self.canv.drawString(fillw + 8, 5, txt)

        self.canv.restoreState()


def generate_full_audit_pdf(data, out_path):
    """
    Generates a professional ~5-page International Standard PDF report
    with graphical presentation + optional competitor analysis
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=16*mm,
        leftMargin=16*mm,
        topMargin=20*mm,
        bottomMargin=18*mm
    )

    styles = getSampleStyleSheet()

    h1 = ParagraphStyle('Heading1', parent=styles['Heading1'], fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=14, spaceAfter=8)
    normal = styles['Normal']

    story = []

    # ───────────────────────────────
    #          Page 1 - Cover
    # ───────────────────────────────
    story.append(Spacer(1, 80*mm))
    story.append(Paragraph("<b>CERTIFIED WEBSITE AUDIT REPORT</b>", styles['Title']))
    story.append(Spacer(1, 24))
    story.append(Paragraph(f"URL: {data.get('url', 'N/A')}", h2))
    story.append(Spacer(1, 12))

    overall = data.get('overall_score', 0)
    story.append(Paragraph(f"Global Health Score: {overall}%", h2))
    story.append(Spacer(1, 16))
    story.append(ScoreBar(overall, width=400, height=22))
    story.append(Spacer(1, 60*mm))

    story.append(Paragraph("Professional Export Readiness Assessment", normal))
    story.append(PageBreak())

    # ───────────────────────────────
    #        Page 2 - Summary
    # ───────────────────────────────
    story.append(Paragraph("Summary", h1))
    story.append(Spacer(1, 8))

    categories = data.get('categories', {})

    # Category summary table
    table_data = [["Category", "Score"]]
    cat_names = []
    cat_scores = []

    for name, info in categories.items():
        score = info.get('score', 0)
        table_data.append([name, f"{score}%"])
        cat_names.append(name[:20])
        cat_scores.append(score)

    summary_table = Table(table_data, colWidths=[280, 120])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,1), (1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 7),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 20))

    if cat_scores:
        drawing = Drawing(420, 180)
        bc = HorizontalBarChart()
        bc.x = 80
        bc.y = 30
        bc.height = 130
        bc.width = 320
        bc.data = [cat_scores]
        bc.categoryAxis.categoryNames = cat_names
        bc.categoryAxis.labels.boxAnchor = 'e'
        bc.categoryAxis.labels.dx = -5
        bc.categoryAxis.labels.angle = -30
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars.strokeWidth = 0.5
        bc.bars.fillColor = colors.mediumblue
        drawing.add(bc)
        story.append(drawing)

    story.append(PageBreak())

    # ───────────────────────────────
    #     Competitor Analysis (optional)
    # ───────────────────────────────
    competitors = data.get('competitors', [])
    if competitors:
        story.append(Paragraph("Competitor Analysis", h1))
        story.append(Spacer(1, 10))

        comp_data = [["Website", "Score", "Grade"]]
        comp_names = ["Your Site"]
        comp_scores = [overall]

        for comp in competitors:
            c_url = comp.get('url', 'Competitor')[:25]
            c_score = comp.get('overall_score', 0)
            c_grade = comp.get('grade', '—')
            comp_data.append([c_url, f"{c_score}%", c_grade])
            comp_names.append(c_url)
            comp_scores.append(c_score)

        comp_table = Table(comp_data, colWidths=[240, 100, 80])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 7),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 20))

        # Competitor bar chart
        drawing = Drawing(420, 180)
        bc = HorizontalBarChart()
        bc.x = 80
        bc.y = 30
        bc.height = 130
        bc.width = 320
        bc.data = [comp_scores]
        bc.categoryAxis.categoryNames = comp_names
        bc.categoryAxis.labels.boxAnchor = 'e'
        bc.categoryAxis.labels.dx = -5
        bc.categoryAxis.labels.angle = -30
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars.strokeWidth = 0.5
        bc.bars.fillColor = colors.teal
        drawing.add(bc)
        story.append(drawing)

        story.append(PageBreak())

    # ───────────────────────────────
    #     Category detail pages
    # ───────────────────────────────
    for cat_name, info in categories.items():
        story.append(Paragraph(f"Category: {cat_name}", h1))
        story.append(Spacer(1, 10))

        score = info.get('score', 0)
        story.append(Paragraph(f"Section Health Score: {score}%", h2))
        story.append(Spacer(1, 12))
        story.append(ScoreBar(score, width=400, height=20))
        story.append(Spacer(1, 20))

        metrics = info.get('metrics', {})
        if metrics:
            t_data = [["Metric", "Value"]]
            for k, v in metrics.items():
                nice_name = k.replace('_', ' ').title()
                t_data.append([nice_name, str(v)])

            t = Table(t_data, colWidths=[340, 120])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ALIGN', (1,1), (1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 7),
            ]))
            story.append(t)

        story.append(PageBreak())

    doc.build(story)
    return out_path
