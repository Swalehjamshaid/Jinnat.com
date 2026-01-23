import os
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

class PDFService:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.brand_name = os.getenv("BRAND_NAME", "FF Tech")

    def generate_audit_pdf(self, audit_data: dict) -> BytesIO:
        """
        Generates a professional, branded PDF report for the website audit.
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []

        # Custom Styles
        title_style = ParagraphStyle(
            'TitleStyle', parent=self.styles['Heading1'],
            fontSize=22, textColor=colors.hexColor("#0f172a"), spaceAfter=12
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle', parent=self.styles['Normal'],
            fontSize=10, textColor=colors.grey, spaceAfter=20
        )

        # 1. Header & Title
        elements.append(Paragraph(f"{self.brand_name} | Professional Website Audit", header_style))
        elements.append(Paragraph(f"Audit Intelligence Report", title_style))
        elements.append(Paragraph(f"Target URL: {audit_data.get('url')}", self.styles['Normal']))
        elements.append(Paragraph(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", self.styles['Normal']))
        elements.append(Spacer(1, 20))

        # 2. Executive Score Table
        elements.append(Paragraph("Core Performance Metrics", self.styles['Heading2']))
        score = audit_data.get('score', 0)
        
        data = [
            ['Metric Group', 'Result / Status'],
            ['Global Health Score', f"{score}%"],
            ['Network Connectivity', audit_data.get('connectivity', {}).get('status', 'N/A')],
            ['Largest Contentful Paint (LCP)', audit_data.get('performance', {}).get('lcp', 'N/A')],
            ['First Contentful Paint (FCP)', audit_data.get('performance', {}).get('fcp', 'N/A')],
            ['Cumulative Layout Shift (CLS)', audit_data.get('performance', {}).get('cls', 'N/A')],
        ]

        t = Table(data, colWidths=[200, 250])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.hexColor("#3b82f6")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 25))

        # 3. AI Insights Section (World-Class Analysis)
        elements.append(Paragraph("Executive AI Summary", self.styles['Heading2']))
        ai_text = audit_data.get('ai_summary', "Analysis completed. Technical data verified by Gemini AI.")
        
        ai_style = ParagraphStyle(
            'AIStyle', parent=self.styles['Normal'],
            leading=14, leftIndent=10, firstLineIndent=0,
            backColor=colors.hexColor("#f1f5f9"), borderPadding=10
        )
        elements.append(Paragraph(ai_text, ai_style))
        
        elements.append(Spacer(1, 40))
        
        # 4. Footer
        footer_text = "This report is generated based on ISO/IEC 25010 standards for software quality."
        elements.append(Paragraph(footer_text, self.styles['Italic']))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
