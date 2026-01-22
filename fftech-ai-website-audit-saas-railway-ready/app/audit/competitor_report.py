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
    # Real competitor URLs for Haier PK (electronics/appliances)
    competitors = [
        'https://www.dawlance.com.pk/',
        'https://www.pel.com.pk/',
        'https://www.orient.com.pk/'
    ]

    # Placeholder scores – in real, run run_audit on each competitor
    metrics = {
        "151_Competitor_Health": 74.0,
        "154_SEO_Comparison": "Above Market Average",
        "164_Competitive_Gap": 82,
        "167_Competitive_Rank": "Top 3 in Industry",
        "Competitors_Analyzed": len(competitors)
    }

    return {
        "score": 78.0,
        "metrics": metrics,
        "color": "#6366F1"
    }


def _pick_metric(perf: dict, key: str):
    if not isinstance(perf, dict):
        return None

    psi = perf.get('psi') or {}
    mobile = psi.get('mobile') or {}
    desktop = psi.get('desktop') or {}

    for scope in ('field', 'lab'):
        v = (mobile.get(scope) or {}).get(key)
        if v is not None:
            return v
        v = (desktop.get(scope) or {}).get(key)
        if v is not None:
            return v

    return perf.get(key)


def build_competitor_pdf(comp_result: dict, out_path: str) -> str:
    doc = SimpleDocTemplate(out_path, pagesize=A4)
    story = []

    base_url = comp_result.get('base', {}).get('url')
    base_score = comp_result.get('base', {}).get('result', {}).get('overall_score')

    comps = comp_result.get('competitors', [])

    story.append(Paragraph('<b>Competitor Comparison</b>', styles['Title']))
    story.append(Spacer(1,8))
    story.append(Paragraph(f'Base URL: <b>{base_url}</b>', styles['Normal']))

    labels = [base_url[:24] + ('...' if len(base_url)>24 else '')]
    values = [base_score or 0]
    for c in comps:
        labels.append((c.get('url') or '')[:24] + ('...' if len(c.get('url',''))>24 else ''))
        values.append(c.get('result', {}).get('overall_score') or 0)

    overall_chart = generate_bar(labels, values, 'Overall Score (0-100)', 'competitor_overall.png')
    story.append(Image(overall_chart, width=420, height=210))

    metric_defs = [('lcp_ms','LCP (ms)'),('cls','CLS (score)'),('inp_ms','INP (ms)'),('tbt_ms','TBT (ms)')]

    perf_base = comp_result.get('base', {}).get('result', {}).get('performance', {})
    perf_comps = [(c.get('url'), c.get('result', {}).get('performance', {})) for c in comps]

    for key, title in metric_defs:
        labels = [base_url[:24] + ('...' if len(base_url)>24 else '')]
        values = [_pick_metric(perf_base, key) or 0]

        for u, perf in perf_comps:
            labels.append((u or '')[:24] + ('...' if len((u or ''))>24 else ''))
            values.append(_pick_metric(perf, key) or 0)

        chart_path = generate_bar(labels, values, title, f'cmp_{key}.png')
        story.append(Spacer(1,10))
        story.append(Image(chart_path, width=420, height=210))

    doc.build(story)
    return out_path
