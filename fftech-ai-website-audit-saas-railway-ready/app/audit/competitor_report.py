from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPM

def generate_bar(labels, values, title, out_file):
    width, height, margin = 450, 225, 40
    bar_height, spacing = 20, 10
    scale = (width-2*margin)/max(values) if values else 1
    drawing = Drawing(width, height)
    drawing.add(String(margin, height-20, title, fontSize=14))
    for i, (label, val) in enumerate(zip(labels, values)):
        y = height-margin-(i+1)*(bar_height+spacing)
        drawing.add(Rect(margin, y, val*scale, bar_height))
        drawing.add(String(0, y+5, label, fontSize=8))
        drawing.add(String(margin+val*scale+5, y+5, str(val), fontSize=8))
    renderPM.drawToFile(drawing, out_file, fmt="PNG")
    return out_file

def build_competitor_pdf(comp_result: dict, out_path: str):
    doc = SimpleDocTemplate(out_path)
    story = []
    styles = getSampleStyleSheet()
    base_url = comp_result.get('base', {}).get('url','N/A')
    story.append(Paragraph(f"<b>Audit Report: {base_url}</b>", styles['Title']))
    story.append(Spacer(1,12))
    score = comp_result.get('base', {}).get('result', {}).get('overall_score',0)
    story.append(Paragraph(f"Score: {score}", styles['Normal']))
    doc.build(story)
    return out_path
