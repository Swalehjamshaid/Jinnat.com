# -*- coding: utf-8 -*-
"""
app/audit/pdf_report.py

World-class PDF "Web Report" generator using WeasyPrint (HTML/CSS → PDF).

Why WeasyPrint?
- Supports PDF variants (PDF/A, PDF/UA, etc.) using the pdf_variant option. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
- Can tag PDFs for accessibility using pdf_tags=True. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
- Supports CSS paged media concepts for print-ready layouts (page breaks, headers/footers). [2](https://deepwiki.com/Kozea/WeasyPrint/1-weasyprint-overview)[1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
- Extracts metadata from HTML (<title>, <meta ...>, <html lang=...>) into PDF metadata fields. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)

Exported API:
    generate_audit_pdf(audit_data: dict, output_path: str, logo_path: str|None = None, report_title: str = "...", ...)
"""

from __future__ import annotations

import os
import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

# WeasyPrint provides HTML→PDF and supports PDF/UA and PDF/A variants in options. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except Exception as e:
    raise RuntimeError(
        "WeasyPrint is required for world-class PDF export. "
        "Install: pip install weasyprint (plus system deps for your OS). "
        f"Import error: {e}"
    ) from e


__all__ = ["generate_audit_pdf"]


# -----------------------------
# Small utilities
# -----------------------------

def _ensure_dir(file_path: str) -> None:
    d = os.path.dirname(os.path.abspath(file_path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def _safe_str(v: Any, default: str = "") -> str:
    try:
        if v is None:
            return default
        s = str(v)
        return s if s.strip() else default
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(n)))


def _html_escape(s: str) -> str:
    s = s or ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;"))


def _iso_date(v: Optional[str] = None) -> str:
    # WeasyPrint can store created/modified metadata from dcterms meta tags. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    if v and isinstance(v, str) and v.strip():
        return v.strip()
    return _dt.date.today().isoformat()


def _score_band(score: Any) -> Tuple[str, str]:
    """Return (label, hex_color)"""
    s = _clamp(_safe_int(score, 0))
    if s >= 90:
        return "Excellent", "#16a34a"
    if s >= 75:
        return "Good", "#22c55e"
    if s >= 60:
        return "Fair", "#f59e0b"
    return "Needs Improvement", "#ef4444"


def _svg_score_bar(categories: List[Tuple[str, int]]) -> str:
    """
    Inline SVG (vector) score chart.
    - Inline SVG keeps things crisp and print-friendly.
    - Provide <title>/<desc> for assistive technology hints.
    """
    # basic sizing
    w, h = 760, 240
    pad_l, pad_r, pad_t, pad_b = 60, 20, 30, 40
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    n = max(1, len(categories))
    bar_gap = 14
    bar_w = int((chart_w - (n - 1) * bar_gap) / n)
    max_val = 100

    # build bars
    bars = []
    labels = []
    for i, (name, val) in enumerate(categories):
        x = pad_l + i * (bar_w + bar_gap)
        v = _clamp(val)
        bh = int((v / max_val) * chart_h)
        y = pad_t + (chart_h - bh)
        band, color = _score_band(v)

        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="10" fill="{color}"></rect>'
        )
        labels.append(
            f'<text x="{x + bar_w/2:.1f}" y="{h - 18}" text-anchor="middle" '
            f'font-size="12" fill="#0f172a">{_html_escape(name)}</text>'
        )
        labels.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y - 8}" text-anchor="middle" '
            f'font-size="12" fill="#0f172a">{v}</text>'
        )

    # y-axis ticks
    ticks = []
    for t in [0, 25, 50, 75, 100]:
        ty = pad_t + (chart_h - int((t / 100) * chart_h))
        ticks.append(f'<line x1="{pad_l-10}" y1="{ty}" x2="{w-pad_r}" y2="{ty}" stroke="#e5e7eb" stroke-width="1"/>')
        ticks.append(f'<text x="{pad_l-16}" y="{ty+4}" text-anchor="end" font-size="11" fill="#64748b">{t}</text>')

    return f"""
<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Score Breakdown Chart" xmlns="http://www.w3.org/2000/svg">
  <title>Score Breakdown</title>
  <desc>Bar chart showing category scores out of 100.</desc>
  <rect x="0" y="0" width="{w}" height="{h}" rx="18" fill="#ffffff" stroke="#e5e7eb"/>
  {''.join(ticks)}
  {''.join(bars)}
  {''.join(labels)}
</svg>
""".strip()


def _list_items(items: Any) -> List[str]:
    if not items:
        return []
    if isinstance(items, list):
        return [x for x in (_safe_str(i, "") for i in items) if x.strip()]
    return [x for x in _safe_str(items, "").split("\n") if x.strip()]


# -----------------------------
# CSS (print-ready, brandable)
# -----------------------------

def _build_css() -> str:
    """
    CSS Paged Media:
    - @page for margins + page counters for page numbers (supported by WeasyPrint). [2](https://deepwiki.com/Kozea/WeasyPrint/1-weasyprint-overview)[1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    """
    return r"""
/* ---------- Page / Print ---------- */
@page {
  size: A4;
  margin: 18mm 16mm 20mm 16mm;

  @bottom-left {
    content: string(doc-title);
    color: #475569;
    font-size: 9pt;
  }

  @bottom-right {
    content: "Page " counter(page) " of " counter(pages);
    color: #475569;
    font-size: 9pt;
  }
}

/* ---------- Base ---------- */
:root{
  --ink:#0f172a;
  --muted:#475569;
  --border:#e5e7eb;
  --bg:#f8fafc;
  --brand:#0ea5e9;
  --ok:#16a34a;
  --warn:#f59e0b;
  --bad:#ef4444;
  --card:#ffffff;
}

html, body{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, "Noto Sans", "Liberation Sans", sans-serif;
  color: var(--ink);
  font-size: 11pt;
  line-height: 1.45;
}

* { box-sizing: border-box; }

a { color: var(--brand); text-decoration: none; }
a:hover { text-decoration: underline; }

.small { font-size: 9.5pt; color: var(--muted); }
.muted { color: var(--muted); }

hr { border: 0; border-top: 1px solid var(--border); margin: 14px 0; }

.page-break { break-before: page; }

/* ---------- Cover ---------- */
.cover {
  padding: 18mm 14mm;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 55%, #f8fafc 100%);
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo {
  width: 56px;
  height: 56px;
  object-fit: contain;
}

.cover h1 {
  font-size: 24pt;
  line-height: 1.1;
  margin: 0 0 6px 0;
}

.cover .meta {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 18px;
}

.meta .kv {
  background: rgba(255,255,255,0.9);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px 12px;
}

.kv .k { font-size: 9.2pt; color: var(--muted); }
.kv .v { font-size: 11pt; font-weight: 600; margin-top: 2px; }

/* ---------- Headings ---------- */
h2 {
  font-size: 14.5pt;
  margin: 18px 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

h3 {
  font-size: 12.5pt;
  margin: 14px 0 8px;
}

h1, h2, h3 { break-after: avoid; }

/* Create PDF bookmarks from headings where supported */
h2 { bookmark-level: 1; bookmark-label: content(text); }
h3 { bookmark-level: 2; bookmark-label: content(text); }

/* ---------- Cards / Grid ---------- */
.grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 12px;
}

.card{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 12px 12px;
}

.badge{
  display:inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 9.5pt;
  border: 1px solid var(--border);
  background: #fff;
  margin-left: 6px;
}

.badge.ok { border-color: rgba(22,163,74,.25); background: rgba(22,163,74,.08); color: #166534; }
.badge.warn { border-color: rgba(245,158,11,.25); background: rgba(245,158,11,.10); color: #92400e; }
.badge.bad { border-color: rgba(239,68,68,.25); background: rgba(239,68,68,.08); color: #991b1b; }

/* ---------- Tables ---------- */
table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
}

thead th {
  background: #0ea5e9;
  color: #fff;
  font-weight: 700;
  font-size: 10pt;
  padding: 10px;
  text-align: left;
}

tbody td {
  padding: 9px 10px;
  border-top: 1px solid var(--border);
  vertical-align: top;
}

tbody tr:nth-child(even) td { background: #f8fafc; }

/* ---------- Lists ---------- */
ul { margin: 6px 0 0 18px; }
li { margin: 4px 0; }

/* ---------- Footer note ---------- */
.note {
  font-size: 9.3pt;
  color: var(--muted);
  border-left: 4px solid #cbd5e1;
  padding: 8px 10px;
  background: #f8fafc;
  border-radius: 10px;
}
""".strip()


# -----------------------------
# HTML template (semantic)
# -----------------------------

def _build_html(
    audit_data: Dict[str, Any],
    *,
    report_title: str,
    logo_path: Optional[str],
    lang: str,
    generator_name: str,
    keywords: Optional[List[str]],
) -> str:
    website = audit_data.get("website") or {}
    client = audit_data.get("client") or {}
    brand = audit_data.get("brand") or {}
    audit = audit_data.get("audit") or {}
    scores = audit_data.get("scores") or {}
    scope = audit_data.get("scope") or {}
    seo_block = audit_data.get("seo") or {}
    perf_block = audit_data.get("performance") or {}

    website_name = _safe_str(website.get("name"), "N/A")
    website_url = _safe_str(website.get("url"), "N/A")
    industry = _safe_str(website.get("industry"), "N/A")
    audience = _safe_str(website.get("audience"), "N/A")
    goals = _list_items(website.get("goals"))

    client_name = _safe_str(client.get("name"), "N/A")
    brand_name = _safe_str(brand.get("name"), "N/A")

    audit_date = _iso_date(_safe_str(audit.get("date"), ""))
    overall_score = _clamp(_safe_int(audit.get("overall_score"), 0))
    grade = _safe_str(audit.get("grade"), "N/A")
    verdict = _safe_str(audit.get("verdict"), "N/A")
    exec_summary = _safe_str(audit.get("executive_summary"), "")

    key_risks = _list_items(audit.get("key_risks"))
    opportunities = _list_items(audit.get("opportunities"))

    # Category scores (runner_result_to_audit_data currently sets seo/performance/security; others may be None)
    seo = scores.get("seo")
    performance = scores.get("performance")
    security = scores.get("security")
    ux_ui = scores.get("ux_ui")
    accessibility = scores.get("accessibility")
    content_quality = scores.get("content_quality")

    def fmt_score(v: Any) -> str:
        if v is None or v == "":
            return "N/A"
        try:
            return str(_clamp(int(v)))
        except Exception:
            return "N/A"

    # label and badge class by overall score
    overall_label, overall_color = _score_band(overall_score)
    overall_badge_cls = "ok" if overall_score >= 75 else ("warn" if overall_score >= 60 else "bad")

    # Findings
    seo_on_page = _list_items(seo_block.get("on_page_issues"))
    seo_tech = _list_items(seo_block.get("technical_issues"))
    perf_issues = _list_items(perf_block.get("page_size_issues"))

    what = _list_items(scope.get("what"))
    why = _safe_str(scope.get("why"), "")
    tools = _list_items(scope.get("tools"))

    # SVG chart (vector)
    chart_svg = _svg_score_bar([
        ("SEO", _safe_int(seo, 0) if seo is not None else 0),
        ("Performance", _safe_int(performance, 0) if performance is not None else 0),
        ("Security", _safe_int(security, 0) if security is not None else 0),
        ("Accessibility", _safe_int(accessibility, 0) if accessibility is not None else 0),
    ])

    # logo file URL (WeasyPrint resolves local paths using base_url or file://)
    logo_html = ""
    if logo_path and os.path.exists(logo_path):
        # alt text is required for accessibility expectations (Tagged PDF best practices). [3](https://pdfa.org/resource/iso-14289-pdfua/)[4](https://www.iso.org/standard/64599.html)
        logo_html = f'<img class="logo" src="{_html_escape(logo_path)}" alt="{_html_escape(brand_name)} logo" />'

    # Keywords/meta
    kw = ", ".join(keywords or [])

    # Store doc title for footer via CSS strings
    # WeasyPrint reads metadata from <title> and <meta ...> and language from <html lang>. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    html = f"""
<!doctype html>
<html lang="{_html_escape(lang)}">
<head>
  <meta charset="utf-8">
  <title>{_html_escape(report_title)}</title>

  <meta name="author" content="{_html_escape(brand_name)}">
  <meta name="description" content="Website audit report for { _html_escape(website_url) }">
  <meta name="keywords" content="{_html_escape(kw)}">
  <meta name="generator" content="{_html_escape(generator_name)}">

  <!-- W3C profile of ISO8601 date strings are supported in metadata fields by WeasyPrint. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html) -->
  <meta name="dcterms.created" content="{_html_escape(audit_date)}">
  <meta name="dcterms.modified" content="{_html_escape(audit_date)}">

  <style>
    /* CSS injected from Python for single-file reliability */
  </style>
</head>

<body>

<!-- Cover -->
<section class="cover" aria-label="Cover Page">
  <div class="brand-row">
    {logo_html}
    <div>
      <h1 style="string-set: doc-title content();">{_html_escape(report_title)}</h1>
      <div class="small">
        <span><b>Brand:</b> {_html_escape(brand_name)}</span> &nbsp; • &nbsp;
        <span><b>Client:</b> {_html_escape(client_name)}</span>
      </div>
      <div class="small">
        <span><b>Date:</b> {_html_escape(audit_date)}</span>
      </div>
    </div>
  </div>

  <hr>

  <div class="meta" role="group" aria-label="Report Metadata">
    <div class="kv"><div class="k">Website</div><div class="v">{_html_escape(website_name)}</div></div>
    <div class="kv"><div class="k">URL</div><div class="v">{_html_escape(website_url)}</div></div>
    <div class="kv"><div class="k">Industry</div><div class="v">{_html_escape(industry)}</div></div>
    <div class="kv"><div class="k">Audience</div><div class="v">{_html_escape(audience)}</div></div>

    <div class="kv">
      <div class="k">Overall Score</div>
      <div class="v">
        {overall_score} / 100
        <span class="badge {overall_badge_cls}">{_html_escape(overall_label)}</span>
      </div>
    </div>

    <div class="kv"><div class="k">Grade</div><div class="v">{_html_escape(grade)}</div></div>
    <div class="kv"><div class="k">Verdict</div><div class="v">{_html_escape(verdict)}</div></div>
    <div class="kv"><div class="k">Prepared by</div><div class="v">{_html_escape(brand_name)}</div></div>
  </div>

  <hr>

  <div class="small">
    <b>Goals:</b>
    {"<ul>" + "".join(f"<li>{_html_escape(g)}</li>" for g in goals) + "</ul>" if goals else "<span class='muted'>N/A</span>"}
  </div>
</section>

<div class="page-break"></div>

<!-- Executive Summary -->
<section aria-label="Executive Summary">
  <h2>Executive Summary</h2>
  <p>{_html_escape(exec_summary) if exec_summary else "This report summarizes automated health checks across SEO, performance, link structure, and security."}</p>

  <div class="grid" role="group" aria-label="Summary Cards">
    <div class="card">
      <h3>Overall Result</h3>
      <p><b>{overall_score}/100</b> • Grade <b>{_html_escape(grade)}</b> • Verdict <b>{_html_escape(verdict)}</b></p>
      <p class="small muted">This is an automated report. Prioritize improvements based on business goals and user impact.</p>
    </div>

    <div class="card">
      <h3>Score Breakdown</h3>
      <div aria-label="Score chart">
        {chart_svg}
      </div>
      <p class="small muted">Scores are heuristic indicators to guide prioritization.</p>
    </div>
  </div>
</section>

<!-- Category Scores Table -->
<section aria-label="Category Scores">
  <h2>Category Scores</h2>

  <table role="table" aria-label="Category Scores Table">
    <thead>
      <tr>
        <th scope="col">Category</th>
        <th scope="col">Score</th>
        <th scope="col">Interpretation</th>
      </tr>
    </thead>
    <tbody>
      { _row("SEO", seo) }
      { _row("Performance", performance) }
      { _row("Security", security) }
      { _row("UX/UI", ux_ui) }
      { _row("Accessibility", accessibility) }
      { _row("Content Quality", content_quality) }
    </tbody>
  </table>
</section>

<!-- Risks & Opportunities -->
<section aria-label="Key Risks and Opportunities">
  <h2>Key Risks</h2>
  { _ul(key_risks) }

  <h2>Opportunities</h2>
  { _ul(opportunities) }
</section>

<!-- Findings -->
<section aria-label="Detailed Findings">
  <h2>SEO Findings</h2>
  <h3>On-Page Issues</h3>
  { _ul(seo_on_page) }
  <h3>Technical Issues</h3>
  { _ul(seo_tech) }

  <h2>Performance Findings</h2>
  <h3>Performance & Page Size</h3>
  { _ul(perf_issues) }
</section>

<div class="page-break"></div>

<!-- Methodology -->
<section aria-label="Scope and Methodology">
  <h2>Scope & Methodology</h2>
  <h3>What we checked</h3>
  { _ul(what) }

  <h3>Why it matters</h3>
  <p>{_html_escape(why) if why else "N/A"}</p>

  <h3>Tools & Approach</h3>
  { _ul(tools) }

  <div class="note" role="note" aria-label="Important Note">
    <b>Note:</b> Automated checks do not replace manual review. For accessibility and compliance claims,
    validate output using appropriate tooling and perform manual QA.
  </div>
</section>

<!-- Appendix -->
<section aria-label="Appendix">
  <h2>Appendix</h2>
  <p class="small muted">
    Generated by {_html_escape(generator_name)} on {_html_escape(audit_date)}.
    This PDF uses semantic structure and optional tagging to support accessibility workflows.
  </p>
</section>

</body>
</html>
""".strip()

    # helper functions injected into template (simple safe string formatting)
    def _interpret(v: Any) -> str:
        if v is None or v == "":
            return "Not assessed"
        try:
            s = _clamp(int(v))
            label, _ = _score_band(s)
            return label
        except Exception:
            return "Not assessed"

    def _row(cat: str, v: Any) -> str:
        sc = fmt_score(v)
        interp = _interpret(v)
        return f"<tr><td>{_html_escape(cat)}</td><td><b>{_html_escape(sc)}</b></td><td>{_html_escape(interp)}</td></tr>"

    def _ul(items: List[str]) -> str:
        if not items:
            return "<p class='muted'>None identified.</p>"
        return "<ul>" + "".join(f"<li>{_html_escape(x)}</li>" for x in items) + "</ul>"

    # Replace placeholders by calling helpers
    html = html.replace("{ _ul(key_risks) }", _ul(key_risks))
    html = html.replace("{ _ul(opportunities) }", _ul(opportunities))
    html = html.replace("{ _ul(seo_on_page) }", _ul(seo_on_page))
    html = html.replace("{ _ul(seo_tech) }", _ul(seo_tech))
    html = html.replace("{ _ul(perf_issues) }", _ul(perf_issues))
    html = html.replace("{ _ul(what) }", _ul(what))
    html = html.replace("{ _ul(tools) }", _ul(tools))

    html = html.replace("{ _row(\"SEO\", seo) }", _row("SEO", seo))
    html = html.replace("{ _row(\"Performance\", performance) }", _row("Performance", performance))
    html = html.replace("{ _row(\"Security\", security) }", _row("Security", security))
    html = html.replace("{ _row(\"UX/UI\", ux_ui) }", _row("UX/UI", ux_ui))
    html = html.replace("{ _row(\"Accessibility\", accessibility) }", _row("Accessibility", accessibility))
    html = html.replace("{ _row(\"Content Quality\", content_quality) }", _row("Content Quality", content_quality))

    return html


# -----------------------------
# Public API
# -----------------------------

def generate_audit_pdf(
    *,
    audit_data: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    report_title: str = "Website Audit Report",
    brand_generator: str = "FF Tech Website Audit Pro",
    lang: str = "en",
    pdf_variant: str = "pdf/ua-1",
    # pdf_variant choices include pdf/ua-1, pdf/ua-2, pdf/a-2u, etc. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    tag_pdf: bool = True,
    include_srgb_profile: bool = True,
    embed_full_fonts: bool = True,
    keywords: Optional[List[str]] = None,
    base_url: Optional[str] = None,
) -> str:
    """
    Generate a high-end, print-ready audit PDF.

    Parameters
    ----------
    audit_data : dict
        The dict structure produced by runner_result_to_audit_data() in runner.py
    output_path : str
        Path to write PDF
    logo_path : str|None
        Optional logo image path
    report_title : str
        PDF title
    lang : str
        Document language (BCP 47). Extracted from <html lang> into metadata. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    pdf_variant : str
        e.g. "pdf/ua-1" for accessible PDF, or "pdf/a-2u" for archival + unicode mapping. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    tag_pdf : bool
        Whether to enable PDF tagging. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    include_srgb_profile : bool
        Include sRGB profile for consistent color management. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)le. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    base_url : str|None
        Base URL for resolving relative assets (images/fonts).

    Returns
    -------
    str : output_path
    """
    if not isinstance(audit_data, dict):
        raise ValueError("audit_data must be a dict")
    if not output_path or not isinstance(output_path, str):
        raise ValueError("output_path must be a non-empty string")

    _ensure_dir(output_path)

    css_text = _build_css()
    html_text = _build_html(
        audit_data,
        report_title=report_title,
        logo_path=logo_path,
        lang=lang,
        generator_name=brand_generator,
        keywords=keywords or ["website audit", "seo", "performance", "security", "accessibility", "report"],
    )

    # Inject CSS into HTML <style> to keep single-file reliability
    html_text = html_text.replace(
        "<style>\n    /* CSS injected from Python for single-file reliability */\n  </style>",
        f"<style>\n{css_text}\n</style>"
    )

    font_config = FontConfiguration()

    # WeasyPrint options include pdf_variant, pdf_tags, custom_metadata, srgb, full_fonts. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    # Enable custom_metadata so HTML meta tags end up in PDF info fields. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    options = {
        "pdf_variant": pdf_variant,
        "pdf_tags": bool(tag_pdf),
        "custom_metadata": True,
        "srgb": bool(include_srgb_profile),
        "full_fonts": bool(embed_full_fonts),
        # Reasonable defaults for reports:
        "optimize_images": True,
        "jpeg_quality": 90,
    }

    # Base URL helps resolve local logo paths + any future assets. [1](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
    doc = HTML(string=html_text, base_url=base_url or os.getcwd())
    doc.write_pdf(
        output_path,
        stylesheets=[CSS(string=css_text, font_config=font_config)],
        font_config=font_config,
        **options
    )
    return output_path
