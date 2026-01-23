
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from pptx import Presentation
from pptx.util import Inches

ASSETS_DIR = Path('generated_assets')
ASSETS_DIR.mkdir(exist_ok=True)

def generate_charts(audit_result: dict) -> str:
    fig, ax = plt.subplots(figsize=(6,3))
    cats = list(audit_result.get('breakdown', {}).keys())
    vals = [audit_result['breakdown'][k] for k in cats]
    ax.bar(cats, vals, color=['#2E86DE','#58D68D','#F5B041'])
    ax.set_title('Category Scores')
    ax.set_ylim(0, 100)
    chart_path = ASSETS_DIR / 'category_scores.png'
    fig.tight_layout()
    fig.savefig(chart_path, dpi=150)
    plt.close(fig)
    return str(chart_path)

def generate_bar(labels, values, title, filename):
    fig, ax = plt.subplots(figsize=(6,3))
    ax.bar(labels, values, color=['#2E86DE'] + ['#58D68D']*(len(labels)-1))
    ax.set_title(title)
    upper = max([v for v in values if isinstance(v,(int,float))] + [0])
    ax.set_ylim(0, max(100, upper))
    fig.tight_layout()
    out = ASSETS_DIR / filename
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)

def export_xlsx(audit_result: dict) -> str:
    df = pd.json_normalize(audit_result)
    path = ASSETS_DIR / 'audit_summary.xlsx'
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Summary')
    return str(path)

def export_pptx(audit_result: dict, chart_path: str) -> str:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = 'FF Tech - Website Audit Summary'
    slide.placeholders[1].text = f"Overall Score: {audit_result.get('overall_score', 0)} - Grade {audit_result.get('grade')}"
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    s2.shapes.add_picture(chart_path, Inches(1), Inches(1), height=Inches(4))
    path = ASSETS_DIR / 'audit_deck.pptx'
    prs.save(path)
    return str(path)
