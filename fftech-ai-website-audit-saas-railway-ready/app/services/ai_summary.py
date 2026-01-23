
import requests
from ..settings import get_settings

def _build_prompt(audit: dict) -> str:
    br = audit.get('breakdown', {})
    perf = audit.get('performance', {})
    onp = audit.get('onpage', {})
    links = audit.get('links', {})
    overall = audit.get('overall_score')
    grade = audit.get('grade')
    return (
        "You are an SEO audit assistant. Write a 180-220 word executive summary for a client-ready report. "
        f"Overall score: {overall}, Grade: {grade}. "
        f"Category scores (0-100): Performance={br.get('performance')}, On-page={br.get('onpage')}, Coverage={br.get('coverage')}. "
        f"Key performance (ms): LCP={perf.get('lcp_ms')}, FCP={perf.get('fcp_ms')}, TBT={perf.get('tbt_ms')}. "
        f"On-page flags: missing_titles={onp.get('missing_title_tags')}, missing_meta={onp.get('missing_meta_descriptions')}. "
        f"Links: broken_total={links.get('total_broken_links')}. "
        "Structure into: Strengths, Weaknesses, and Top 3 Priorities (imperative verbs)."
    )

def generate_exec_summary(audit: dict) -> str | None:
    s = get_settings()
    if not s.GOOGLE_GEMINI_API_KEY:
        return None
    model = s.GEMINI_MODEL or 'models/gemini-2.5-flash'
    url = f'https://generativelanguage.googleapis.com/v1beta/{model}:generateContent'
    body = { 'contents': [ { 'parts': [ { 'text': _build_prompt(audit) } ] } ] }
    try:
        r = requests.post(url, headers={'x-goog-api-key': s.GOOGLE_GEMINI_API_KEY, 'Content-Type':'application/json'}, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        cand = (data.get('candidates') or [{}])[0]
        parts = ((cand.get('content') or {}).get('parts') or [{}])
        txt = ''
        for p in parts:
            if 'text' in p:
                txt += p.get('text','')
        return txt.strip() or None
    except Exception:
        return None
