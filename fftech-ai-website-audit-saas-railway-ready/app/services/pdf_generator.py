import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
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
    def __init__(self, score, width=440, height=26, max_score=100):
        Flowable.__init__(self)
        self.score = min(max(float(score or 0), 0), max_score)
        self.width = width
        self.height = height
        self.max_score = max_score

    def wrap(self, *args):
        return self.width, self.height + 10

    def draw(self):
        self.canv.saveState()
        self.canv.setFillColor(colors.lightgrey)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)

        fillw = (self.score / self.max_score) * self.width
        col = (
            colors.green if self.score >= 85 else
            colors.limegreen if self.score >= 70 else
            colors.orange if self.score >= 50 else
            colors.red
        )
        self.canv.setFillColor(col)
        self.canv.rect(0, 0, fillw, self.height, fill=1, stroke=0)

        self.canv.setStrokeColor(colors.black)
        self.canv.rect(0, 0, self.width, self.height, fill=0, stroke=1)

        self.canv.setFont("Helvetica-Bold", 12)
        txt = f"{self.score:.1f}%"
        if fillw > 70:
            self.canv.setFillColor(colors.white)
            self.canv.drawCentredString(fillw / 2, 8, txt)
        else:
            self.canv.setFillColor(colors.black)
            self.canv.drawString(fillw + 12, 8, txt)
        self.canv.restoreState()


def generate_full_audit_pdf(data, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=25*mm
    )

    styles = getSampleStyleSheet()

    h1 = ParagraphStyle('Heading1', parent=styles['Heading1'], fontSize=22, spaceAfter=16, textColor=colors.darkblue)
    h2 = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=16, spaceAfter=12)
    normal = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=11, leading=14)

    story = []

    # Cover
    story.append(Spacer(1, 100*mm))
    story.append(Paragraph("<b>CERTIFIED WEBSITE AUDIT REPORT</b>", styles['Title']))
    story.append(Spacer(1, 36))
    story.append(Paragraph(f"Website: {data.get('url', 'N/A')}", h2))
    story.append(Spacer(1, 16))

    overall = float(data.get('overall_score', 0) or 0)
    grade = data.get('grade', 'B')
    story.append(Paragraph(f"Global Health Score: {overall:.2f}%", h2))
    story.append(Paragraph(f"Final Grade: {grade}", h2))
    story.append(Spacer(1, 24))
    story.append(ScoreBar(overall, width=440, height=28))
    story.append(Spacer(1, 80*mm))

    story.append(Paragraph("Comprehensive Export Readiness Assessment — 2026", normal))
    story.append(PageBreak())

    # Executive Summary
    story.append(Paragraph("Executive Summary", h1))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Analyzed website: {data.get('url', 'N/A')}", normal))
    story.append(Spacer(1, 20))

    categories = data.get('categories', {})

    table_data = [["Category", "Score", "Status"]]
    cat_names = []
    cat_scores = []

    for name, info in categories.items():
        score = float(info.get('score', 0) or 0)
        status = "Excellent" if score >= 85 else "Good" if score >= 70 else "Needs Attention" if score >= 50 else "Critical"
        table_data.append([name, f"{score:.1f}%", status])
        cat_names.append(name[:20])
        cat_scores.append(score)

    summary_table = Table(table_data, colWidths=[260, 90, 130])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.7, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 28))

    if cat_scores:
        story.append(Paragraph("Category Performance Overview", h2))
        drawing = Drawing(460, 200)
        bc = HorizontalBarChart()
        bc.x = 100
        bc.y = 40
        bc.height = 150
        bc.width = 350
        bc.data = [cat_scores]
        bc.categoryAxis.categoryNames = cat_names
        bc.categoryAxis.labels.boxAnchor = 'e'
        bc.categoryAxis.labels.dx = -8
        bc.categoryAxis.labels.dy = -2
        bc.categoryAxis.labels.angle = -40
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars.strokeWidth = 0.7
        bc.bars.fillColor = colors.navy
        drawing.add(bc)
        story.append(drawing)

    story.append(PageBreak())

    # Competitor section
    story.append(Paragraph("Competitor Benchmarking", h1))
    story.append(Spacer(1, 14))

    competitors = data.get('competitors', [])
    if competitors:
        comp_data = [["Website", "Score", "Grade"]]
        comp_names = ["This Site"]
        comp_scores = [overall]

        for comp in competitors:
            c_url = comp.get('url', 'Competitor')[:30]
            c_score = float(comp.get('overall_score', 0) or 0)
            c_grade = comp.get('grade', '—')
            comp_data.append([c_url, f"{c_score:.1f}%", c_grade])
            comp_names.append(c_url[:20])
            comp_scores.append(c_score)

        comp_table = Table(comp_data, colWidths=[280, 100, 80])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.7, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 9),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 28))

        drawing = Drawing(460, 220)
        bc = HorizontalBarChart()
        bc.x = 100
        bc.y = 45
        bc.height = 160
        bc.width = 350
        bc.data = [comp_scores]
        bc.categoryAxis.categoryNames = comp_names
        bc.categoryAxis.labels.boxAnchor = 'e'
        bc.categoryAxis.labels.dx = -8
        bc.categoryAxis.labels.angle = -40
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = 100
        bc.valueAxis.valueStep = 20
        bc.bars.strokeWidth = 0.7
        bc.bars.fillColor = colors.teal
        drawing.add(bc)
        story.append(drawing)
    else:
        story.append(Paragraph("No competitor data available.", normal))
        story.append(Spacer(1, 20))
        story.append(Paragraph("Provide 3–5 competitor URLs for benchmarking.", normal))

    story.append(PageBreak())

    # Category Details
    for cat_name, info in categories.items():
        story.append(Paragraph(f"Category: {cat_name}", h1))
        story.append(Spacer(1, 14))

        score = float(info.get('score', 0) or 0)
        story.append(Paragraph(f"Health Score: {score:.1f}%", h2))
        story.append(Spacer(1, 16))
        story.append(ScoreBar(score, width=440, height=26))
        story.append(Spacer(1, 28))

        metrics = info.get('metrics', {})
        if metrics:
            t_data = [["Metric", "Value"]]
            for k, v in metrics.items():
                nice_name = k.replace('_', ' ').title()
                t_data.append([nice_name, str(v)])

            t = Table(t_data, colWidths=[380, 140])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.7, colors.grey),
                ('ALIGN', (1,1), (1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 9),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTSIZE', (0,0), (-1,-1), 11),
            ]))
            story.append(t)
            story.append(Spacer(1, 20))

        story.append(PageBreak())

    # Recommendations
    story.append(Paragraph("Recommendations & Conclusion", h1))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "This audit evaluates export readiness across technical, performance, and international dimensions. "
        "The score highlights strengths and priority areas for global competitiveness.",
        normal
    ))
    story.append(Spacer(1, 20))

    story.append(Paragraph("Key Recommendations:", h2))
    story.append(Spacer(1, 10))
    recs = [
        "Prioritize Core Web Vitals (LCP, CLS, INP) and server response time",
        "Fix missing titles, meta descriptions, thin content, and broken links",
        "Enable HTTPS and review security headers",
        "Add multilingual support (hreflang) and export pages (shipping, customs)",
        "Re-audit monthly and benchmark against competitors",
        "Use AI for content & technical optimization"
    ]
    for rec in recs:
        story.append(Paragraph(f"• {rec}", normal))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 30))
    story.append(Paragraph("Thank you for using FFTech Certified Audit Service.", normal))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Generated on: January 2026 | support@fftech.ai", normal))

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path
