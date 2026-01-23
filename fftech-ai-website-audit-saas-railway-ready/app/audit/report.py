
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from pathlib import Path
from .record import generate_charts
from ..settings import get_settings

styles = getSampleStyleSheet()

def build_pdf(audit_result: dict, out_path: str) -> str:
    settings = get_settings()
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    story = []
    logo_path = settings.BRAND_LOGO_PATH
    if Path(logo_path).exists():
        story.append(Image(logo_path, width=140, height=40))
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Executive Summary</b>', styles['Title']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Overall Score: <b>{audit_result.get('overall_score',0)}</b> - Grade <b>{audit_result.get('grade','D')}</b>", styles['Normal']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(audit_result.get('executive_summary','Auto-generated audit report.'), styles['BodyText']))
    story.append(Spacer(1, 12))
    story.append(Paragraph('Conclusion: Your site has clear opportunities for improvement in the next sprint.', styles['Italic']))
    story.append(Spacer(1, 24))
    story.append(Paragraph('<b>Category Breakdown</b>', styles['Heading2']))
    chart_path = generate_charts(audit_result)
    story.append(Image(chart_path, width=420, height=210))
    story.append(Paragraph('Conclusion: Focus on the lowest-scoring category first.', styles['Italic']))
    story.append(Spacer(1, 24))
    story.append(Paragraph('<b>Issues Overview</b>', styles['Heading2']))
    issues = [['Metric', 'Value']]
    for k, v in (audit_result.get('issues_overview') or {}).items():
        issues.append([k, str(v)])
    t = Table(issues, colWidths=[240, 240])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    story.append(t)
    story.append(Paragraph('Conclusion: Address high-impact errors first.', styles['Italic']))
    story.append(Spacer(1, 24))
    story.append(Paragraph('<b>Performance Snapshot</b>', styles['Heading2']))
    perf = audit_result.get('performance', {})
    perf_tbl = [['Metric', 'Value']] + [[k, str(v)] for k, v in perf.items()]
    t2 = Table(perf_tbl, colWidths=[240, 240])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    story.append(t2)
    story.append(Paragraph('Conclusion: Optimize images, enable compression, and reduce JS payload.', styles['Italic']))
    story.append(Spacer(1, 24))
    story.append(Paragraph('<b>Priorities & Roadmap</b>', styles['Heading2']))
    prios = audit_result.get('priorities', ['Fix broken links', 'Add missing meta descriptions', 'Improve LCP under 2.5s'])
    prio_tbl = [['Priority Items']] + [[p] for p in prios]
    t3 = Table(prio_tbl, colWidths=[480])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    story.append(t3)
    story.append(Paragraph('Conclusion: Execute quick wins in week 1, plan structural fixes over the next 30 days.', styles['Italic']))
    doc.build(story)
    return out_path
