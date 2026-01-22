import os
import time
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

def generate_full_audit_pdf(data, out_path):
    """
    CATEGORY A - METRIC 10: Certified Export Readiness.
    Generates a comprehensive 5-page international standard PDF report.
    """
    # Ensure reports directory exists in the container
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # --- PAGE 1: COVER ---
    story.append(Spacer(1, 100))
    story.append(Paragraph("<b>CERTIFIED WEBSITE AUDIT REPORT</b>", styles['Title']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"URL: {data.get('url', 'N/A')}", styles['Normal']))
    story.append(Paragraph(f"Global Health Score: {data.get('overall_score', 0)}%", styles['Heading2']))
    story.append(Paragraph(f"Final Grade: {data.get('grade', 'B')}", styles['Heading2']))
    story.append(PageBreak())

    # --- PAGES 2-5: CATEGORY BREAKDOWNS ---
    categories = data.get('categories', {})
    for cat_name, info in categories.items():
        story.append(Paragraph(f"Category Analysis: {cat_name}", styles['Heading1']))
        story.append(Paragraph(f"Section Score: {info.get('score', 0)}%", styles['Heading3']))
        story.append(Spacer(1, 10))
        
        # Metric Table Construction
        t_data = [["Metric ID & Description", "Value"]]
        metrics = info.get('metrics', {})
        for key, val in metrics.items():
            t_data.append([key, str(val)])
            
        t = Table(t_data, colWidths=[350, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
        story.append(t)
        story.append(PageBreak())

    doc.build(story)
    return out_path
