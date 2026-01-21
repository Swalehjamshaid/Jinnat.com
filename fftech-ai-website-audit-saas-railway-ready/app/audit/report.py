import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle

# Corrected absolute imports
from app.audit.record import generate_charts
from app.settings import get_settings

styles = getSampleStyleSheet()

def build_pdf(audit_id, url, overall_score, grade, category_scores, metrics, storage_dir):
    """
    Builds a professional PDF audit report.
    Matched to the arguments sent by app/api/router.py.
    """
    settings = get_settings()
    out_path = f"{storage_dir}/audit_{audit_id}.pdf"
    
    # Ensure the storage directory exists on the Railway server
    os.makedirs(storage_dir, exist_ok=True)
    
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    story = []
    
    # 1. Branding Logo
    logo_path = settings.BRAND_LOGO_PATH
    if Path(logo_path).exists():
        story.append(Image(logo_path, width=140, height=40))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph(f'<b>Website Audit Report: {url}</b>', styles['Title']))
    story.append(Spacer(1, 12))
    
    # 2. Executive Summary
    story.append(Paragraph('<b>Executive Summary</b>', styles['Heading2']))
    story.append(Spacer(1, 6))
    summary_text = f"Overall Score: <b>{overall_score}</b> | Grade: <b>{grade}</b>"
    story.append(Paragraph(summary_text, styles['Normal']))
    
    story.append(Spacer(1, 12))
    
    # 3. Category Breakdown (Chart Generation)
    story.append(Paragraph('<b>Category Breakdown</b>', styles['Heading2']))
    story.append(Spacer(1, 12))
    
    # Preparing dictionary for the chart generator
    chart_data = {
        "category_scores": category_scores,
        "overall_score": overall_score
    }
    
    try:
        # Calls generate_charts from .record
        chart_path = generate_charts(chart_data)
        if Path(chart_path).exists():
            story.append(Image(chart_path, width=420, height=210))
    except Exception as e:
        story.append(Paragraph(f"<i>Chart generation skipped: {str(e)}</i>", styles['Italic']))

    story.append(Spacer(1, 24))
    
    # 4. Metrics Overview Table
    story.append(Paragraph('<b>Issues & Metrics Overview</b>', styles['Heading2']))
    issues_data = [['Metric', 'Value']]
    
    # Unpack metrics dictionary into table rows
    for k, v in metrics.items():
        issues_data.append([k.replace('_', ' ').title(), str(v)])
        
    t = Table(issues_data, colWidths=[240, 240])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
    ]))
    story.append(t)
    
    story.append(Spacer(1, 24))
    
    # 5. Roadmap
    story.append(Paragraph('<b>Priorities & Roadmap</b>', styles['Heading2']))
    prios = ['Fix broken links', 'Optimize images', 'Improve mobile LCP']
    prio_tbl = [['Priority Items']] + [[p] for p in prios]
    
    t3 = Table(prio_tbl, colWidths=[480])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    story.append(t3)
    
    # Finalize and build
    doc.build(story)
    return out_path
