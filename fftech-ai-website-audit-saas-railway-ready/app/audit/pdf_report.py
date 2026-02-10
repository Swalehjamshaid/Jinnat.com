# -*- coding: utf-8 -*-
"""
app/audit/pdf_report.py
World-class 5-page PDF Audit Report generator using WeasyPrint.
- Beautiful, print-ready layout with colors, graphs, and organized text
- 5 structured pages: Cover, Summary + Graph, Category Scores, Highlights + Details, Notes
- Full integration with runner.py data (overall_score, grade, breakdown, chart_data, dynamic)
- Supports logo, accessibility tags, and metadata
"""

from __future__ import annotations
import os
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except ImportError as e:
    raise RuntimeError(
        "WeasyPrint is required for professional PDF reports. "
        "Install: pip install weasyprint (plus system deps: cairo, pango, gdk-pixbuf)"
    ) from e

__all__ = ["generate_audit_pdf"]

# ========================================
# Utilities
# ========================================

def _safe_str(v: Any, default: str = "N/A") -> str:
    try:
        return str(v).strip() or default
    except:
        return default

def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except:
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

def _score_color(score: int) -> str:
    s = _clamp(score)
    if s >= 90: return "#16a34a"  # Excellent - green
    if s >= 80: return "#22c55e"  # Good
    if s >= 70: return "#f59e0b"  # Fair - yellow
    return "#ef4444"              # Needs Improvement - red

def _svg_score_chart(categories: List[Dict[str, Any]]) -> str:
    """Inline SVG bar chart for scores - colored and organized"""
    w, h = 760, 280
    pad = 60
    chart_w = w - pad * 2
    chart_h = h - pad * 2
    n = len(categories)
    bar_w = chart_w // n - 20
    max_val = 100

    bars = []
    labels = []
    for i, cat in enumerate(categories):
        name = cat.get("name", "Category")
        val = _safe_int(cat.get("score", 0))
        color = _score_color(val)
        x = pad + i * (bar_w + 40)
        bh = (val / max_val) * chart_h
        y = pad + chart_h - bh
        bars.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="12" fill="{color}"/>')
        labels.append(f'<text x="{x + bar_w/2}" y="{h - 20}" text-anchor="middle" font-size="14" fill="#fff">{name}</text>')
        labels.append(f'<text x="{x + bar_w/2}" y="{y - 10}" text-anchor="middle" font-size="16" fill="#fff"><b>{val}</b></text>')

    return f"""
<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" rx="20" fill="#1e293b"/>
  {''.join(bars)}
  {''.join(labels)}
</svg>
""".strip()

# ========================================
# CSS – Professional, Print-Ready, Colored
# ========================================

def _build_css() -> str:
    return """
@page {
  size: A4;
  margin: 2cm 1.8cm 2.5cm 1.8cm;
  @top-center { content: "Website Audit Report"; font-size: 10pt; color: #64748b; }
  @bottom-center { content: "Page " counter(page) " of " counter(pages); font-size: 9pt; color: #64748b; }
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: #0f172a;
  font-size: 11pt;
  line-height: 1.5;
  margin: 0;
}
h1 { font-size: 28pt; margin: 0; color: #0d6efd; }
h2 { font-size: 18pt; margin: 1.2em 0 0.6em; color: #1e293b; border-bottom: 2px solid #e2e8f0; }
h3 { font-size: 14pt; margin: 1em 0 0.4em; color: #334155; }
p, li { margin: 0.6em 0; }
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
}
th, td {
  padding: 10px;
  border: 1px solid #e2e8f0;
  text-align: left;
}
th { background: #0d6efd; color: white; font-weight: 600; }
tr:nth-child(even) { background: #f8fafc; }
.score-card {
  background: linear-gradient(135deg, #f8fafc, #ffffff);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.2em;
  margin: 0.8em 0;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.badge {
  padding: 6px 12px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 10pt;
}
.good { background: #22c55e; color: white; }
.fair { background: #f59e0b; color: white; }
.bad { background: #ef4444; color: white; }
.page-break { page-break-before: always; }
.cover {
  text-align: center;
  padding: 4cm 0 2cm;
  background: linear-gradient(to bottom, #eff6ff, #ffffff);
}
    """.strip()

# ========================================
# Build HTML – 5-Page Structure with Graphs, Colors, Organized Text
# ========================================

def _build_html(audit_data: Dict[str, Any], report_title: str, logo_path: str = None) -> str:
    data = audit_data or {}
    overall_score = _safe_int(data.get("overall_score", 0))
    grade = _safe_str(data.get("grade", "N/A"))
    audited_url = _safe_str(data.get("audited_url", "N/A"))
    breakdown = data.get("breakdown", {})
    dynamic = data.get("dynamic", {})
    chart_data = data.get("chart_data", [{}])[0].get("data", {})

    # Category scores with extras
    categories = [
        {"name": "SEO", "score": breakdown.get("seo", {}).get("score", 0), "extras": breakdown.get("seo", {}).get("extras", {})},
        {"name": "Performance", "score": breakdown.get("performance", {}).get("score", 0), "extras": breakdown.get("performance", {}).get("extras", {})},
        {"name": "Links", "score": breakdown.get("links", {}).get("score", 0), "extras": breakdown.get("links", {})},
        {"name": "Security", "score": breakdown.get("security", {}).get("score", 0), "extras": breakdown.get("security", {})},
    ]

    chart_svg = _svg_score_chart(categories)

    # Category table rows with colors
    category_rows = ""
    for cat in categories:
        score = cat["score"]
        color_cls = 'good' if score >= 80 else 'fair' if score >= 70 else 'bad'
        category_rows += f"""
        <tr>
            <th>{cat["name"]}</th>
            <td><span class="badge {color_cls}">{score}</span></td>
        </tr>
        """

    # Extras details (organized)
    seo_extras = breakdown.get("seo", {}).get("extras", {})
    perf_extras = breakdown.get("performance", {}).get("extras", {})
    links_extras = breakdown.get("links", {})
    sec_extras = breakdown.get("security", {})

    extras_html = f"""
    <h3>SEO Details</h3>
    <p>Title: {seo_extras.get("title", "N/A")}</p>
    <p>Meta Description: {seo_extras.get("meta_description_present", "N/A")}</p>
    <p>Canonical: {seo_extras.get("canonical", "N/A")}</p>
    <p>H1 Count: {seo_extras.get("h1_count", "N/A")}</p>
    <p>Images Total: {seo_extras.get("images_total", "N/A")}</p>
    <p>Images Missing Alt: {seo_extras.get("images_missing_alt", "N/A")}</p>
    
    <h3>Performance Details</h3>
    <p>Load Time: {perf_extras.get("load_ms", "N/A")} ms</p>
    <p>Page Size: {perf_extras.get("bytes", "N/A")} bytes</p>
    <p>Scripts: {perf_extras.get("scripts", "N/A")}</p>
    <p>Styles: {perf_extras.get("styles", "N/A")}</p>
    <p>Fetcher: {perf_extras.get("fetcher", "N/A")}</p>
    
    <h3>Links Details</h3>
    <p>Internal Links: {links_extras.get("internal_links_count", "N/A")}</p>
    <p>External Links: {links_extras.get("external_links_count", "N/A")}</p>
    <p>Total Links: {links_extras.get("total_links_count", "N/A")}</p>
    
    <h3>Security Details</h3>
    <p>HTTPS: {sec_extras.get("https", "N/A")}</p>
    <p>HSTS: {sec_extras.get("hsts", "N/A")}</p>
    <p>Status Code: {sec_extras.get("status_code", "N/A")}</p>
    <p>Server: {sec_extras.get("server", "N/A")}</p>
    """

    # Highlights cards (colored and organized)
    cards_html = ""
    for card in dynamic.get("cards", []):
        title = _html_escape(card.get("title", "N/A"))
        body = _html_escape(card.get("body", "N/A"))
        cards_html += f"""
        <div class="score-card">
            <h3>{title}</h3>
            <p>{body}</p>
        </div>
        """

    # KV table rows with colors for values
    kv_rows = ""
    for item in dynamic.get("kv", []):
        key = _html_escape(item.get("key", "N/A"))
        value = _html_escape(str(item.get("value", "N/A")))
        color_cls = 'good' if "true" in value.lower() or _safe_int(value, 0) > 0 else ''
        kv_rows += f"<tr><th>{key}</th><td class=\"{color_cls}\">{value}</td></tr>"

    logo_tag = f'<img src="{logo_path}" style="max-width:120px; margin-bottom:1em;" alt="Logo">' if logo_path else ""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{_html_escape(report_title)}</title>
<style>{_build_css()}</style>
</head>
<body>

<!-- Page 1: Cover -->
<div class="cover">
    {logo_tag}
    <h1>{_html_escape(report_title)}</h1>
    <p style="font-size:14pt; margin:1em 0;"><b>Audited URL:</b> {audited_url}</p>
    <div style="font-size:32pt; color:{_score_color(overall_score)}; margin:1.5em 0;">
        {overall_score} / 100 <span style="font-size:24pt;">({grade})</span>
    </div>
    <p style="font-size:16pt; color:#334155;">Generated on {dt.date.today().strftime('%B %d, %Y')}</p>
</div>

<div class="page-break"></div>

<!-- Page 2: Executive Summary + Graph -->
<h2>Executive Summary</h2>
<p>This report provides a comprehensive audit of the website based on SEO, Performance, Links, and Security metrics. Overall performance is rated <span style="color:{_score_color(overall_score)};">{grade}</span> with a score of <b>{overall_score}/100</b>.</p>

<h3>Score Breakdown</h3>
<div style="text-align:center;">
    {chart_svg}
</div>

<div class="page-break"></div>

<!-- Page 3: Category Scores -->
<h2>Category Scores</h2>
<table>
    <thead><tr><th>Category</th><th>Score</th></tr></thead>
    <tbody>{category_rows}</tbody>
</table>

<div class="page-break"></div>

<!-- Page 4: Highlights + Details -->
<h2>Highlights</h2>
<div style="display:grid; grid-template-columns:repeat(2,1fr); gap:1em;">
    {cards_html}
</div>

<h2>Detailed Information</h2>
<table>
    <thead><tr><th>Property</th><th>Value</th></tr></thead>
    <tbody>{kv_rows}</tbody>
</table>

<div class="page-break"></div>

<!-- Page 5: Detailed Findings + Notes -->
<h2>Detailed Findings</h2>
{extras_html}

<h2>Notes & Methodology</h2>
<p>This report was generated automatically using advanced web auditing tools. Scores are indicative and should be reviewed in context of business goals. Contact FF Tech for manual audit services.</p>
<p style="text-align:center; margin-top:4cm; color:#64748b; font-size:10pt;">
    © FF Tech Website Audit Pro | Confidential Report | {dt.date.today().strftime('%Y')}
</p>

</body>
</html>
""".strip()

# ========================================
# Public API (unchanged)
# ========================================

def generate_audit_pdf(
    *,
    audit_data: Dict[str, Any],
    output_path: str,
    logo_path: Optional[str] = None,
    report_title: str = "Website Audit Report",
    lang: str = "en",
    pdf_variant: str = "pdf/ua-1",
    tag_pdf: bool = True,
) -> str:
    """
    Generate a 5-page world-class PDF audit report using WeasyPrint.
    Returns the output_path.
    """
    if not isinstance(audit_data, dict):
        raise ValueError("audit_data must be a dict")

    if not output_path:
        raise ValueError("output_path is required")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    html_content = _build_html(audit_data, report_title, logo_path)
    css_content = _build_css()

    font_config = FontConfiguration()

    HTML(string=html_content).write_pdf(
        output_path,
        stylesheets=[CSS(string=css_content, font_config=font_config)],
        font_config=font_config,
    )

    if not os.path.exists(output_path):
        raise RuntimeError("PDF was not generated")

    return output_path
