import os
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

class PDFService:
    def __init__(self):
        """
        Initializes the PDF generator with international branding standards.
        """
        self.styles = getSampleStyleSheet()
        self.brand_name = os.getenv("BRAND_NAME", "FF Tech")

    def generate_audit_pdf(self, audit_data: dict) -> BytesIO:
        """
        Generates a branded, executive-level PDF report.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4, 
            rightMargin=40, 
            leftMargin=40, 
            topMargin=40, 
            bottomMargin=40
        )
        elements = []

        # Premium Typography Styles
        title_style = ParagraphStyle(
            'TitleStyle', parent=self.styles['Heading1'],
            fontSize=24, textColor=colors.hexColor("#0f172a"), 
            spaceAfter=10, fontName="Helvetica-Bold"
        )

        # 1. Header Section
        elements.append(Paragraph(f"{self.brand_name} Audit Intelligence", title_style))
        elements.append(Paragraph(f"URL: {audit_data.get('url')}", self.styles['Normal']))
        elements.append(Paragraph(f"Analysis Date: {datetime.now().strftime('%B %d, %Y')}", self.styles['Normal']))
        elements.append(Spacer(1, 24))

        # 2. Key Metrics Table
        elements.append(Paragraph("Technical Performance Breakdown", self.styles['Heading2']))
        score = audit_data.get('score', 0)
        
        data = [
            ['Metric Category', 'Result'],
            ['Overall Health Score', f"{score}%"],
            ['Connectivity Status', audit_data.get('connectivity', {}).get('status', 'Unknown')],
            ['LCP (Speed)', audit_data.get('performance', {}).get('lcp', 'N/A')],
            ['FCP (Render)', audit_data.get('performance', {}).get('fcp', 'N/A')]
        ]

        t = Table(data, colWidths=[200, 240])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#3b82f6")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 24))

        # 3. AI Executive Insights
        elements.append(Paragraph("Executive AI Insights", self.styles['Heading2']))
        ai_text = audit_data.get('ai_summary', "Standard technical analysis completed.")
        
        # Highlighted Box for AI Insights
        ai_box_style = ParagraphStyle(
            'AIBox', parent=self.styles['Normal'],
            backColor=colors.hexColor("#eff6ff"),
            borderPadding=12, leading=14
        )
        elements.append(Paragraph(ai_text, ai_box_style))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
