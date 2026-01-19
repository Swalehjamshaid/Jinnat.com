from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm


def build_pdf(data) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    overall = data.get('overall', {})
    metrics = data.get('metrics', {})

    c.setTitle('Website Audit Report')
    c.setFont('Helvetica-Bold', 18)
    c.drawString(2*cm, height-3*cm, 'Website Audit Report')

    c.setFont('Helvetica', 12)
    y = height-4*cm
    for k in ['score', 'grade', 'coverage']:
        c.drawString(2*cm, y, f"{k.capitalize()}: {overall.get(k, '-')}")
        y -= 0.7*cm

    c.setFont('Helvetica-Bold', 14)
    c.drawString(2*cm, y-0.5*cm, 'Metrics')
    y -= 1.5*cm
    c.setFont('Helvetica', 12)
    for k, v in metrics.items():
        c.drawString(2*cm, y, f"{k}: {v}")
        y -= 0.6*cm
        if y < 2*cm:
            c.showPage()
            y = height-2*cm

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()
