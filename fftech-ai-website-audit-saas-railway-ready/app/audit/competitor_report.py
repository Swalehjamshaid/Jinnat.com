# app/audit/competitor_report.py

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
import os

# Use an absolute import to ensure reliability across different environments
try:
    from app.audit.record import generate_bar
except ImportError:
    from .record import generate_bar

styles = getSampleStyleSheet()

def _pick_metric(perf: dict, key: str):
    """
    Safely extracts metrics from complex PSI (PageSpeed Insights) structures.
    Checks Mobile Field/Lab, then Desktop Field/Lab, then root keys.
    """
    if not isinstance(perf, dict):
        return 0

    psi = perf.get('psi') or {}
    mobile = psi.get('mobile') or {}
    desktop = psi.get('desktop') or {}

    # Priority 1 & 2: Mobile Field and Lab data
    for scope in ('field', 'lab'):
        v = (mobile.get(scope) or {}).get(key)
        if v is not None:
            return v
            
    # Priority 3 & 4: Desktop Field and Lab data
    for scope in ('field', 'lab'):
        v = (desktop.get(scope) or {}).get(key)
        if v is not None:
            return v
            
    # Fallback: Root key or 0
    return perf.get(key) or 0

def build_competitor_pdf(comp_result: dict, out_path: str) -> str:
    """
    Constructs a PDF report comparing a base URL against multiple competitors.
    """
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    story = []

    # Extract base site information
    base_url = comp_result.get('base', {}).get('url', 'N/A')
    base_res = comp_result.get('base', {}).get('result', {})
    base_score = base_res.get('overall_score', 0)
    comps = comp_result.get('competitors', [])

    # Header section
    story.append(Paragraph('<b>Competitor Comparison Report</b>', styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f'Target Site: <b>{base_url}</b>', styles['Normal']))
    story.append(Paragraph(f'Generated on: 2026-01-24', styles['Normal']))
    story.append(Spacer(1, 15))

    # --- Section 1: Overall Score Comparison ---
    story.append(Paragraph('<b>Overall Performance Benchmark</b>', styles['Heading2']))
    
    labels = [base_url[:24] + ('...' if len(base_url) > 24 else '')]
    values = [base_score]
    
    for c in comps:
        url_raw = c.get('url') or 'Unknown'
        url_label = url_raw[:24] + ('...' if len(url_raw) > 24 else '')
        labels.append(url_label)
        values.append(c.get('result', {}).get('overall_score', 0))

    # Generate the bar chart for overall scores
    overall_chart = generate_bar(labels, values, 'Overall Score (0-100)', 'competitor_overall.png')
    story.append(Image(overall_chart, width=450, height=225))
    story.append(Spacer(1, 20))

    # --- Section 2: Core Web Vitals Comparison ---
    story.append(Paragraph('<b>Core Web Vitals Breakdown</b>', styles['Heading2']))
    
    metric_defs = [
        ('lcp_ms', 'LCP - Speed (ms)'),
        ('cls', 'CLS - Stability (score)'),
        ('fcp_ms', 'FCP - Response (ms)'),
        ('tbt_ms', 'TBT - Interactive (ms)')
    ]

    perf_base = base_res.get('performance', {})
    perf_comps = [(c.get('url'), c.get('result', {}).get('performance', {})) for c in comps]

    for key, title in metric_defs:
        labels = [base_url[:24] + ('...' if len(base_url) > 24 else '')]
        values = [_pick_metric(perf_base, key)]
        
        for url, perf in perf_comps:
            url_raw = url or 'Unknown'
            url_label = url_raw[:24] + ('...' if len(url_raw) > 24 else '')
            labels.append(url_label)
            values.append(_pick_metric(perf, key))
            
        # Generate metric-specific chart
        chart_path = generate_bar(labels, values, title, f'cmp_{key}.png')
        story.append(Spacer(1, 10))
        story.append(Paragraph(f'Metric: {title}', styles['Italic']))
        story.append(Image(chart_path, width=420, height=210))

    # Build the final PDF
    doc.build(story)
    return out_path
