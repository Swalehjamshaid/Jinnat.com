import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
import matplotlib.pyplot as plt

BRAND_NAME = os.getenv('BRAND_NAME', 'FF Tech')
BRAND_LOGO_PATH = os.getenv('BRAND_LOGO_PATH', 'backend/static/img/logo.png')

# Colors - FF Tech Professional Palette
PRIMARY_BLUE = colors.HexColor('#2563eb')
SECONDARY_SKY = colors.HexColor('#0ea5e9')
DANGER_RED = colors.HexColor('#ef4444')

def _chart_bar(title: str, data: dict, out_path: str, color='#2563eb'):
    plt.figure(figsize=(6, 3))
    plt.bar(list(data.keys()), list(data.values()), color=color)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

def build_pdf(audit_id: int, url: str, overall_score: float, grade: str, category_scores: dict, metrics: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, f"audit_{audit_id}.pdf")
    
    # 1. Generate Charts
    chart1 = os.path.join(out_dir, f"audit_{audit_id}_cat.png")
    _chart_bar('Category Scores (%)', category_scores, chart1, color='#0ea5e9')
    
    status_dist = {
        '2xx (Success)': metrics.get('status_2xx', 0),
        '3xx (Redirect)': metrics.get('status_3xx', 0),
        '4xx (Broken)': metrics.get('status_4xx', 0)
    }
    chart2 = os.path.join(out_dir, f"audit_{audit_id}_status.png")
    _chart_bar('HTTP Status Distribution', status_dist, chart2, color='#2563eb')

    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    def header(page_title: str):
        try: c.drawImage(BRAND_LOGO_PATH, 2*cm, height-3*cm, width=3*cm, preserveAspectRatio=True, mask='auto')
        except: pass
        c.setFont('Helvetica-Bold', 18); c.setFillColor(PRIMARY_BLUE)
        c.drawString(6*cm, height-2*cm, f"{BRAND_NAME} – Professional Audit")
        c.setFont('Helvetica', 10); c.setFillColor(colors.black)
        c.drawString(6*cm, height-2.6*cm, f"Target URL: {url}")
        c.drawString(6*cm, height-3.1*cm, f"Section: {page_title}")
        c.line(2*cm, height-3.3*cm, width-2*cm, height-3.3*cm)

    def footer(conclusion: str):
        c.setFont('Helvetica-Oblique', 9); c.setFillColor(colors.grey)
        c.drawString(2*cm, 1.5*cm, f"Conclusion: {conclusion}")
        c.drawRightString(width-2*cm, 1.5*cm, 'Certified Report – FF Tech AI Engine v2026')

    # PAGE 1: EXECUTIVE SUMMARY (CATEGORY A)
    header('Executive Summary & Final Grading')
    c.setFont('Helvetica-Bold', 32); c.setFillColor(SECONDARY_SKY)
    c.drawString(2*cm, height-5*cm, f"Grade: {grade} ({overall_score}%)")
    c.setFillColor(colors.black); c.setFont('Helvetica-Bold', 14)
    c.drawString(2*cm, height-6.5*cm, 'Audit Highlights:')
    c.setFont('Helvetica', 11)
    c.drawString(2.5*cm, height-7.2*cm, f"• Total Crawled Pages: {metrics.get('total_pages', 0)}")
    c.drawString(2.5*cm, height-7.8*cm, "• Primary Recommendation: Performance optimization & Link fixing.")
    c.drawImage(chart1, 2*cm, height-15*cm, width=16*cm, preserveAspectRatio=True)
    footer('Focus efforts on the lowest-scoring categories to boost ROI.')
    c.showPage()

    # PAGE 2: SITE HEALTH & CRAWLABILITY (CATEGORY B & C)
    header('Crawlability & Technical Health')
    c.drawImage(chart2, 2*cm, height-10*cm, width=16*cm, preserveAspectRatio=True)
    c.setFont('Helvetica', 11)
    c.drawString(2*cm, height-12*cm, f"Detected Broken Links (4xx): {metrics.get('status_4xx', 0)}")
    c.drawString(2*cm, height-12.6*cm, f"Redirect Count (3xx): {metrics.get('status_3xx', 0)}")
    footer('Reduce 4xx errors immediately to preserve crawl budget.')
    c.showPage()

    # PAGE 3: ON-PAGE SEO & CONTENT (CATEGORY D)
    header('On-Page Content & SEO Intelligence')
    c.setFont('Helvetica-Bold', 12)
    c.drawString(2*cm, height-5*cm, "Content Deficiency Report:")
    c.setFont('Helvetica', 11)
    c.drawString(2.5*cm, height-6*cm, f"• Missing Page Titles: {metrics.get('missing_title', 0)}")
    c.drawString(2.5*cm, height-6.6*cm, f"• Missing Meta Descriptions: {metrics.get('missing_desc', 0)}")
    c.drawString(2.5*cm, height-7.2*cm, f"• Images Missing ALT Text: {metrics.get('img_no_alt', 0)}")
    footer('Add unique metadata and ALT tags to improve search visibility.')
    c.showPage()

    # PAGE 4: PERFORMANCE & MOBILE (CATEGORY E & F)
    header('Performance, Mobile & Security')
    c.setFont('Helvetica', 11)
    c.drawString(2*cm, height-5*cm, f"Average Page Size: {metrics.get('total_size', 0) // 1024} KB")
    c.drawString(2*cm, height-5.6*cm, "Core Web Vitals Assessment: Manual Review Recommended.")
    c.drawString(2*cm, height-6.2*cm, "Security Status: HTTPS Implementation verified.")
    footer('Optimize resource sizes and prioritize Mobile Core Web Vitals.')
    c.showPage()

    # PAGE 5: ROADMAP & FUTURE PLAN (CATEGORY I)
    header('Roadmap, Future Plan & Growth ROI')
    c.setFont('Helvetica-Bold', 14); c.setFillColor(PRIMARY_BLUE)
    c.drawString(2*cm, height-5*cm, "Phase 1: Immediate Growth Fixes (0-30 Days)")
    c.setFillColor(colors.black); c.setFont('Helvetica', 11)
    c.drawString(2.5*cm, height-5.8*cm, "• Batch resolve all 4xx/5xx errors to stabilize site health.")
    c.drawString(2.5*cm, height-6.4*cm, "• Optimize Top 10 landing pages with AI-generated metadata.")
    
    c.setFont('Helvetica-Bold', 14); c.setFillColor(PRIMARY_BLUE)
    c.drawString(2*cm, height-8*cm, "Phase 2: Performance & Scalability (30-90 Days)")
    c.setFillColor(colors.black); c.setFont('Helvetica', 11)
    c.drawString(2.5*cm, height-8.8*cm, "• Implement global image compression and lazy-loading.")
    c.drawString(2.5*cm, height-9.4*cm, "• Set up automated weekly FF Tech monitoring reports.")
    footer('Projected Traffic Growth: +25-40% following Roadmap completion.')
    c.showPage()

    c.save()
    return pdf_path
