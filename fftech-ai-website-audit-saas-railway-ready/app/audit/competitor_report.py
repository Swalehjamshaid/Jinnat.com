from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from .record import generate_bar

styles = getSampleStyleSheet()


def run_competitor_audit(url: str):
    """
    CATEGORY G: COMPETITOR ANALYSIS (151-167)
    Provides data for the graphical web dashboard.
    """
    # Placeholder / example values — in real implementation these would come from actual competitor analysis
    metrics = {
        "151_Competitor_Health": 74.0,
        "154_SEO_Comparison": "Above Market Average",
        "156_Speed_Advantage_ms": 420,              # example: faster than average competitor
        "158_Content_Quality_Index": 82,
        "161_Backlink_Strength": "Moderate",
        "164_Competitive_Gap": 82,
        "167_Competitive_Rank": "Top 3 in Industry"
    }

    return {
        "score": 78.0,
        "metrics": metrics,
        "color": "#6366F1"
    }


def _pick_metric(perf: dict, key: str):
    """
    Safely extract a metric value from nested performance structure.
    Tries multiple paths (mobile/lab/field/desktop).
    """
    if not isinstance(perf, dict):
        return None

    # Try PSI structure paths
    psi = perf.get('psi') or {}
    for scope in ('mobile', 'desktop'):
        scope_data = psi.get(scope) or {}
        for level in ('field', 'lab'):
            v = (scope_data.get(level) or {}).get(key)
            if v is not None:
                return v

    # Fallback to direct key (e.g. legacy or flattened data)
    return perf.get(key)


def build_competitor_pdf(comp_result: dict, out_path: str) -> str:
    """
    Generates a clean competitor comparison PDF report.
    """
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    story = []

    # ───────────────────────────────
    # Header
    # ───────────────────────────────
    story.append(Paragraph('<b>Competitor Comparison Report</b>', styles['Title']))
    story.append(Spacer(1, 8))

    base = comp_result.get('base', {})
    base_url = base.get('url', 'N/A')
    base_score = base.get('result', {}).get('overall_score', 0)

    story.append(Paragraph(f'Base Website: <b>{base_url}</b> (Score: {base_score:.1f})', styles['Normal']))
    story.append(Spacer(1, 12))

    # ───────────────────────────────
    # Overall Score Bar Chart
    # ───────────────────────────────
    comps = comp_result.get('competitors', [])

    labels = [base_url[:24] + ('...' if len(base_url) > 24 else '')]
    values = [base_score]

    for c in comps:
        c_url = c.get('url', 'Competitor')[:24] + ('...' if len(c.get('url', '')) > 24 else '')
        c_score = c.get('result', {}).get('overall_score', 0)
        labels.append(c_url)
        values.append(c_score)

    overall_chart = generate_bar(
        labels=labels,
        values=values,
        title='Overall Health Score Comparison',
        filename='competitor_overall.png'
    )
    story.append(Image(overall_chart, width=440, height=220))
    story.append(Spacer(1, 16))

    # ───────────────────────────────
    # Core Web Vitals Comparison Charts
    # ───────────────────────────────
    metric_defs = [
        ('lcp_ms',   'Largest Contentful Paint (ms) – lower is better'),
        ('cls',      'Cumulative Layout Shift – lower is better'),
        ('inp_ms',   'Interaction to Next Paint (ms) – lower is better'),
        ('tbt_ms',   'Total Blocking Time (ms) – lower is better'),
        ('fcp_ms',   'First Contentful Paint (ms) – lower is better'),
    ]

    perf_base = comp_result.get('base', {}).get('result', {}).get('performance', {})

    for key, title in metric_defs:
        labels = [base_url[:24] + ('...' if len(base_url) > 24 else '')]
        values = [_pick_metric(perf_base, key) or 0]

        for c in comps:
            c_url = c.get('url', '')[:24] + ('...' if len(c.get('url', '')) > 24 else '')
            perf = c.get('result', {}).get('performance', {})
            values.append(_pick_metric(perf, key) or 0)
            labels.append(c_url)

        chart_path = generate_bar(
            labels=labels,
            values=values,
            title=title,
            filename=f'cmp_{key}.png'
        )

        story.append(Paragraph(f'<b>{title}</b>', styles['Heading2']))
        story.append(Spacer(1, 6))
        story.append(Image(chart_path, width=440, height=220))
        story.append(Spacer(1, 16))

    # Build PDF
    doc.build(story)
    return out_path
