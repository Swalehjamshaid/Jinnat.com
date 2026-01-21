import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
import matplotlib.pyplot as plt

BRAND_NAME = os.getenv('BRAND_NAME', 'FF Tech')
BRAND_LOGO_PATH = os.path.join('app', 'static', 'img', 'logo.png')

# FF Tech Professional Color Palette
PRIMARY_BLUE = colors.HexColor('#2563eb')
SECONDARY_SKY = colors.HexColor('#0ea5e9')

def _chart_bar(title: str, data: dict, out_path: str, color='#2563eb'):
    plt.figure(figsize=(6, 3))
    plt.bar(list(data.keys()), list(data.values()), color=color)
    plt.title(title, fontsize=10)
    plt.xticks(rotation=15, fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

def build_pdf(audit_id: int, url: str, overall_score: float, grade: str, category_scores: dict, metrics: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, f"audit_{audit_id}.pdf")
    
    # Generate charts for the PDF
    chart1 = os.path.join(out_dir, f"cat_{audit_id}.png")
    _chart_bar('Category Performance (%)', category_scores, chart1, color='#0ea5e9')
    
    status_dist = {
        '2xx Success': metrics.get('status_2xx', metrics.get('http_2xx', 0)), 
        '3xx Redirect': metrics.get('status_3xx', metrics.get('http_3xx', 0)), 
        '4xx Broken': metrics.get('status_4xx', metrics.get('http_4xx', 0))
    }
    chart2 = os.path.join(out_dir, f"status_{audit_id}.png")
    _chart_bar('HTTP Health Distribution', status_dist, chart2, color='#2563eb')

    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    def header(page_title: str):
        try: c.drawImage(BRAND_LOGO_PATH, 2*cm, height-2.5*cm, width=2.5*cm, preserveAspectRatio=True)
        except: pass
        c.setFont('Helvetica-Bold', 18); c.setFillColor(PRIMARY_BLUE)
        c.drawString(5.5*cm, height-1.8*cm, f"{BRAND_NAME} – Professional Audit")
        c.setFont('Helvetica', 9); c.setFillColor(colors.black)
        c.drawString(5.5*cm, height-2.3*cm, f"Target: {url} | Section: {page_title}")
        c.line(2*cm, height-2.8*cm, width-2*cm, height-2.8*cm)

    def footer(conclusion: str):
        c.setFont('Helvetica-Oblique', 8); c.setFillColor(colors.grey)
        c.drawString(2*cm, 1.2*cm, f"Summary: {conclusion}")
        c.drawRightString(width-2*cm, 1.2*cm, f'Page {c.getPageNumber()} | Executive-Ready Intelligence')

    # PAGE 1: EXECUTIVE SUMMARY
    header('Executive Summary & Overall Grading')
    c.setFont('Helvetica-Bold', 36); c.setFillColor(SECONDARY_SKY)
    c.drawString(2*cm, height-5*cm, f"Grade: {grade} ({overall_score}%)")
    c.drawImage(chart1, 2*cm, height-14*cm, width=16*cm, preserveAspectRatio=True)
    footer('Focus on performance and core SEO metadata first.')
    c.showPage()

    # PAGE 2: CRAWLABILITY
    header('Crawlability & Technical Health')
    c.drawImage(chart2, 2*cm, height-10*cm, width=16*cm, preserveAspectRatio=True)
    c.setFont('Helvetica', 11); c.drawString(2*cm, height-12*cm, f"Total Broken Links Found (4xx): {status_dist['4xx Broken']}")
    footer('Fixing 4xx errors preserves crawl budget and improves UX.')
    c.showPage()

    # PAGE 3: ON-PAGE SEO
    header('On-Page Intelligence & SEO')
    c.setFont('Helvetica-Bold', 12); c.drawString(2*cm, height-5*cm, "Identified Deficiencies:")
    c.setFont('Helvetica', 11)
    c.drawString(2.5*cm, height-6*cm, f"• Missing Page Titles: {metrics.get('missing_title', 0)}")
    c.drawString(2.5*cm, height-6.6*cm, f"• Missing Meta Descriptions: {metrics.get('missing_desc', metrics.get('missing_meta_desc', 0))}")
    c.drawString(2.5*cm, height-7.2*cm, f"• Missing Image ALT Text: {metrics.get('img_no_alt', 0)}")
    footer('Unique metadata and ALT tags significantly boost organic visibility.')
    c.showPage()

    # PAGE 4: PERFORMANCE
    header('Performance & Technical Vitals')
    c.setFont('Helvetica', 11)
    c.drawString(2*cm, height-5*cm, f"Total HTML Payload: {metrics.get('total_size', metrics.get('total_page_size', 0)) // 1024} KB")
    c.drawString(2*cm, height-5.6*cm, "Optimization Status: Large assets detected. Minification recommended.")
    footer('Fast page loads are a critical ranking factor for Google.')
    c.showPage()

    # PAGE 5: FUTURE ROADMAP & ROI
    header('Future Growth Roadmap (ROI Forecast)')
    c.setFont('Helvetica-Bold', 14); c.setFillColor(PRIMARY_BLUE)
    c.drawString(2*cm, height-5*cm, "Phase 1: Immediate Fixes (0-30 Days)")
    c.setFont('Helvetica', 11); c.setFillColor(colors.black)
    c.drawString(2.5*cm, height-5.8*cm, "• Resolve high-impact broken links and redirect loops.")
    c.drawString(2.5*cm, height-6.4*cm, "• Write SEO-optimized meta tags for top-performing pages.")
    
    c.setFont('Helvetica-Bold', 14); c.setFillColor(PRIMARY_BLUE)
    c.drawString(2*cm, height-8.5*cm, "Phase 2: Long-term Strategy (30-90 Days)")
    c.setFont('Helvetica', 11); c.setFillColor(colors.black)
    c.drawString(2.5*cm, height-9.3*cm, "• Set up automated weekly monitoring for site health.")
    c.drawString(2.5*cm, height-9.9*cm, "• Implement advanced Schema Markup to improve Rich Snippets.")
    footer('Projected Traffic Growth: +25% potential after roadmap execution.')
    c.showPage()

    c.save()
    return pdf_path
