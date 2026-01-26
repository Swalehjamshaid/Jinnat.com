
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def build_competitor_pdf(comp_result: dict, out_path: str):
    """Tiny PDF example; not used by runner. Keep minimal."""
    doc = SimpleDocTemplate(out_path)
    story = []
    styles = getSampleStyleSheet()
    base_url = comp_result.get('base', {}).get('url','N/A')
    story.append(Paragraph(f'<b>Audit Report: {base_url}</b>', styles['Title']))
    story.append(Spacer(1,12))
    score = comp_result.get('base', {}).get('result', {}).get('overall_score',0)
    story.append(Paragraph(f'Score: {score}', styles['Normal']))
    doc.build(story)
    return out_path
