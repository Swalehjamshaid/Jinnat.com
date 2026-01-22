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
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Custom canvas to add page numbers 'Page X of Y' in footer"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        page_text = f"Page {self._pageNumber} of {page_count} | FFTech Audit Report"
        self.drawRightString(A4[0] - 20*mm, 12*mm, page_text)


class ScoreBar(Flowable):
    """Clean horizontal score bar"""
    def __init__(self, score, width=400, height=20, max_score=100):
        Flowable.__init__(self)
        self.score = min(max(float(score or 0), 0), max_score)
        self.width = width
        self.height = height
        self.max_score = max_score

    def wrap(self, *args):
        return self.width, self.height + 8

    def draw(self):
        self.canv.saveState()
        self.canv.setFillColor(colors.lightgrey)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        fillw = (self.score / self.max_score) * self.width
        col = colors.green if self.score >= 80 else colors.orange if self.score >= 60 else colors.red
        self.canv.setFillColor(col)
        self.canv.rect(0, 0, fillw, self.height, fill=1, stroke=0)
        self.canv.setStrokeColor(colors.black)
        self.canv.rect(0, 0, self.width, self.height, fill=0, stroke=1)
        self.canv.setFont("Helvetica-Bold", 11)
        txt = f"{int(self.score)}%"
        if fillw > 60:
            self.canv.setFillColor(colors.white)
            self.canv.drawCentredString(fillw / 2, 6, txt)
        else:
            self.canv.setFillColor(colors.black)
            self.canv.drawString(fillw + 10, 6, txt)
        self.canv.restoreState()


def generate_full_audit_pdf(data, out_path):
    """
    Generates a professional ~5-page International Standard PDF report
    with graphical presentation + competitor analysis + conclusion page
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=18*mm,
        leftMargin=18*mm,
        topMargin=22*mm,
        bottomMargin=22*mm
    )

    styles = getSampleStyleSheet()

    h1 = ParagraphStyle('Heading1', parent=styles['Heading1'], fontSize=20, spaceAfter=14, textColor=colors.darkblue)
    h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=15, spaceAfter=10)
    normal = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=11, leading=14)

    story = []

    # Page 1 - Cover
    story.append(Spacer(1, 90*mm))
    story.append(Paragraph("<b>CERTIFIED WEBSITE AUDIT REPORT</b>", styles['Title']))
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"Website: {data.get('url', 'N/A')}", h2))
    story.append(Spacer(1, 14))

    overall = data.get('overall_score', 0)
    grade = data.get('grade', 'B')
    story.append(Paragraph(f"Global Health Score: {overall}%", h2))
    story.append(Paragraph(f"Final Grade: {grade}", h2))
    story.append(Spacer(1, 20))
    story.append(ScoreBar(overall, width=420, height=24))
    story.append(Spacer(1, 70*mm))

    story.append(Paragraph("Comprehensive Export Readiness Assessment — 2026", normal))
    story.append(PageBreak())

    # Page 2 - Summary & Categories Overview
    story.append(Paragraph("Executive Summary", h1))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Analyzed website: {data.get('url', 'N/A')}", normal))
    story.append(Spacer(1, 16))

    categories = data.get('categories', {})

    table_data = [["Category", "Score", "Status"]]
    cat_names = []
    cat_scores = []

    for name, info in categories.items():
        score = info.get('score', 0)
        status = "Excellent" if score >= 85 else "Good" if score >= 70 else "Needs Attention" if score >= 50 else "Critical"
        table_data.append([name, f"{score}%", status])
        cat_names.append(name[:18])
        cat_scores.append(score)

    summary_table = Table(table_data, colWidths=[240, 90, 130])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.6, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 24))

    if cat_scores:
        story.append(Paragraph("Category Performance Overview", h2))
        drawing = Drawing(440, 190)
        bc = HorizontalBarChart()
        bc.x = 90
        bc.y = 35
        bc.height = 140
        bc.width = 340
        bc.data = [cat_scores]
        bc.categoryAxis.categoryNames = cat_names
        bc.categoryAxis.labels.boxAnchor = 'e'
        bc.categoryAxis.labels.dx = -6
        bc.categoryAxis.labels.dy = -2
        bc.categoryAxis.labels.angle = -35
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars.strokeWidth = 0.6
        bc.bars.fillColor = colors.blueviolet
        drawing.add(bc)
        story.append(drawing)

    story.append(PageBreak())

    # Competitor Benchmarking (always present)
    story.append(Paragraph("Competitor Benchmarking", h1))
    story.append(Spacer(1, 12))

    competitors = data.get('competitors', [])
    if competitors:
        comp_data = [["Website", "Score", "Grade"]]
        comp_names = ["This Site"]
        comp_scores = [overall]

        for comp in competitors:
            c_url = comp.get('url', 'Competitor')[:28]
            c_score = comp.get('overall_score', 0)
            c_grade = comp.get('grade', '—')
            comp_data.append([c_url, f"{c_score}%", c_grade])
            comp_names.append(c_url[:18])
            comp_scores.append(c_score)

        comp_table = Table(comp_data, colWidths=[260, 100, 80])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.6, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 24))

        drawing = Drawing(440, 200)
        bc = HorizontalBarChart()
        bc.x = 90
        bc.y = 40
        bc.height = 150
        bc.width = 340
        bc.data = [comp_scores]
        bc.categoryAxis.categoryNames = comp_names
        bc.categoryAxis.labels.boxAnchor = 'e'
        bc.categoryAxis.labels.dx = -6
        bc.categoryAxis.labels.angle = -35
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars.strokeWidth = 0.6
        bc.bars.fillColor = colors.teal
        drawing.add(bc)
        story.append(drawing)
    else:
        story.append(Paragraph("No competitor data available for benchmarking.", normal))
        story.append(Spacer(1, 20))
        story.append(Paragraph("Consider adding competitor URLs and scores to enable this comparison.", normal))

    story.append(PageBreak())

    # Category Details
    for cat_name, info in categories.items():
        story.append(Paragraph(f"Category: {cat_name}", h1))
        story.append(Spacer(1, 12))

        score = info.get('score', 0)
        story.append(Paragraph(f"Health Score: {score}%", h2))
        story.append(Spacer(1, 14))
        story.append(ScoreBar(score, width=420, height=22))
        story.append(Spacer(1, 24))

        metrics = info.get('metrics', {})
        if metrics:
            t_data = [["Metric", "Value"]]
            for k, v in metrics.items():
                nice_name = k.replace('_', ' ').title()
                t_data.append([nice_name, str(v)])

            t = Table(t_data, colWidths=[360, 140])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.6, colors.grey),
                ('ALIGN', (1,1), (1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(t)
            story.append(Spacer(1, 16))

        story.append(PageBreak())

    # Final Page - Recommendations & Conclusion
    story.append(Paragraph("Recommendations & Conclusion", h1))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "This audit evaluates export readiness across key technical and performance dimensions. "
        "Overall score indicates solid foundation with targeted improvements needed in lower-scoring areas.",
        normal
    ))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Key Recommendations:", h2))
    story.append(Spacer(1, 8))
    recs = [
        "Prioritize optimization in categories scoring below 70%",
        "Implement regular monitoring and re-audits every 3-6 months",
        "Compare against top competitors to identify differentiation opportunities",
        "Leverage AI-assisted tools for deeper content and SEO analysis"
    ]
    for rec in recs:
        story.append(Paragraph(f"• {rec}", normal))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 24))
    story.append(Paragraph("Thank you for using this Certified Audit Service.", normal))

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path
