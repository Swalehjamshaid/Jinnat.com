import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

def generate_full_audit_pdf(data, out_path):
    """
    Generates a professional 5-page International Standard PDF report.
    """
    # Ensure reports directory exists in the container
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Page 1: Official Cover
    story.append(Spacer(1, 100))
    story.append(Paragraph("<b>CERTIFIED WEBSITE AUDIT REPORT</b>", styles['Title']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"URL: {data.get('url', 'N/A')}", styles['Normal']))
    story.append(Paragraph(f"Global Health Score: {data.get('overall_score', 0)}%", styles['Heading2']))
    story.append(PageBreak())

    # Pages 2-5: Dynamic Category Breakdown
    categories = data.get('categories', {})
    for cat_name, info in categories.items():
        story.append(Paragraph(f"Category: {cat_name}", styles['Heading1']))
        story.append(Paragraph(f"Section Health Score: {info.get('score', 0)}%", styles['Heading3']))
        
        t_data = [["Metric", "Value"]]
        for k, v in info.get('metrics', {}).items():
            t_data.append([k, str(v)])
            
        t = Table(t_data, colWidths=[350, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        story.append(t)
        story.append(PageBreak())

    doc.build(story)
    return out_path
