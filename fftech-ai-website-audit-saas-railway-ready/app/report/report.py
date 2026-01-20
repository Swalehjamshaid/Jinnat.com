from fpdf import FPDF

class FFTechPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 10)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, 'FF TECH AI AUDIT - CERTIFIED REPORT', 0, 1, 'R')

def build_pdf(data: dict) -> bytes:
    pdf = FFTechPDF()
    pdf.set_auto_page_break(True, margin=15)
    
    # Page 1: High Level Summary
    pdf.add_page()
    pdf.set_font('Arial', 'B', 28)
    pdf.cell(0, 40, f"Score: {data['overall']['score']}%", ln=True)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 10, data['summary'])
    
    # Pages 2-5: Category Detail
    for name, content in data['metrics'].items():
        pdf.add_page()
        pdf.set_font('Arial', 'B', 18)
        pdf.cell(0, 15, name.replace('_', ' ').upper(), ln=True)
        pdf.set_font('Arial', '', 12)
        for k, v in content.items():
            pdf.cell(0, 10, f"{k}: {v}", ln=True)
            
    return pdf.output(dest='S')
