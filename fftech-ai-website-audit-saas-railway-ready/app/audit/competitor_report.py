# app/audit/competitor_report.py

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPM

# Use a local function for bar chart generation (no external dependency)
def generate_bar(labels, values, title, out_file):
    """
    Creates a simple horizontal bar chart as PNG using ReportLab.
    Fully Python-native; no external chart libraries required.
    """
    width = 450
    height = 225
    margin = 40
    bar_height = 20
    spacing = 10

    max_val = max(values) if values else 1
    scale = (width - 2 * margin) / max_val

    drawing = Drawing(width, height)
    drawing.add(String(margin, height - 20, title, fontSize=14))

    for i, (label, val) in enumerate(zip(labels, values)):
        y = height - margin - (i + 1) * (bar_height + spacing)
        # Bar
        drawing.add(Rect(margin, y, val * scale, bar_height, fillColor=None, strokeColor=None))
        # Label
        drawing.add(String(0, y + 5, label, fontSize=8))
        # Value
        drawing.add(String(margin + val * scale + 5, y + 5, str(val), fontSize=8))

    renderPM.drawToFile(drawing, out_file, fmt="PNG")
    return out_file

styles = getSampleStyleSheet()


def _pick_metric(perf: dict, key: str):
    """
    Safely extracts metrics from internal Python-native structures.
    If missing, returns 0.
    """
    if not isinstance(perf, dict):
        return 0
    return perf.get(key, 0)


def build_competitor_pdf(comp_result: dict, out_path: str) -> str:
    """
    Constructs a PDF report comparing a base URL against multiple competitors.
    Entirely Python-native.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    story = []

    # Base site info
    base_url = comp_result.get('base', {}).get('url', 'N/A')
    base_res = comp_result.get('base', {}).get('result', {})
    base_score = base_res.get('overall_score', 0)
    comps = comp_result.get('competitors', [])

    # Header
    story.append(Paragraph('<b>Competitor Comparison Report</b>', styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f'Target Site: <b>{base_url}</b>', styles['Normal']))
    story.append(Paragraph(f'Generated on: 2026-01-24', styles['Normal']))
    story.append(Spacer(1, 15))

    # Overall score comparison
    story.append(Paragraph('<b>Overall Performance Benchmark</b>', styles['Heading2']))
    labels = [base_url[:24] + ('...' if len(base_url) > 24 else '')]
    values = [base_score]

    for c in comps:
        url_raw = c.get('url', 'Unknown')
        labels.append(url_raw[:24] + ('...' if len(url_raw) > 24 else ''))
        values.append(c.get('result', {}).get('overall_score', 0))

    overall_chart = generate_bar(labels, values, 'Overall Score (0-100)', 'competitor_overall.png')
    story.append(Image(overall_chart, width=450, height=225))
    story.append(Spacer(1, 20))

    # Core Web Vitals breakdown
    story.append(Paragraph('<b>Core Web Vitals Breakdown</b>', styles['Heading2']))
    metric_defs = [
        ('lcp_ms', 'LCP - Speed (ms)'),
        ('cls', 'CLS - Stability (score)'),
        ('fcp_ms', 'FCP - Response (ms)'),
        ('tbt_ms', 'TBT - Interactive (ms)')
    ]

    perf_base = base_res.get('performance', {})
    perf_comps = [(c.get('url', 'Unknown'), c.get('result', {}).get('performance', {})) for c in comps]

    for key, title in metric_defs:
        labels = [base_url[:24] + ('...' if len(base_url) > 24 else '')]
        values = [_pick_metric(perf_base, key)]
        for url, perf in perf_comps:
            labels.append(url[:24] + ('...' if len(url) > 24 else ''))
            values.append(_pick_metric(perf, key))

        chart_path = generate_bar(labels, values, title, f'cmp_{key}.png')
        story.append(Spacer(1, 10))
        story.append(Paragraph(f'Metric: {title}', styles['Italic']))
        story.append(Image(chart_path, width=420, height=210))

    doc.build(story)
    return out_path
