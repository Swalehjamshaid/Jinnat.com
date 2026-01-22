from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
import time, os

def generate_full_audit_pdf(data, out_path):
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Page 1: Official Cover
    story.append(Spacer(1, 100))
    story.append(Paragraph("<b>CERTIFIED WEBSITE AUDIT REPORT</b>", styles['Title']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"URL: {data['url']}", styles['Normal']))
    story.append(Paragraph(f"Global Health Score: {data['overall_score']}%", styles['Heading2']))
    story.append(PageBreak())

    # Pages 2-5: Category Detail Sheets
    for cat_name, info in data['categories'].items():
        story.append(Paragraph(f"Category: {cat_name}", styles['Heading1']))
        story.append(Paragraph(f"Health Score: {info['score']}%", styles['Heading3']))
        t_data = [["Metric ID", "Value"]] + [[k, str(v)] for k, v in info['metrics'].items()]
        t = Table(t_data, colWidths=[350, 100])
        t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey), ('GRID', (0,0), (-1,-1), 1, colors.black)]))
        story.append(t)
        story.append(PageBreak())

    doc.build(story)
    return out_path
