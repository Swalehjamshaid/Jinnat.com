"""
fftech-ai-website-audit-saas-railway-ready/app/audit/pdf_report.py

World-class, client-ready PDF generator for the International‑Standard Website Audit.

Key features
------------
- Executive Summary (MANDATORY) with score bars and risk level
- Technical Performance, SEO, Security, Accessibility (CORE & MANDATORY sections)
- Best Practices & UX
- Competitor Benchmarking (PREMIUM)
- Analytics & Tracking
- AI-Driven Insights (ENTERPRISE)
- Prioritized Action Plan (MANDATORY)
- Compliance & Standards Reference (PRO)
- Audit Metadata (PRO)
- Clean, board-ready layout with tables and visual score bars

Usage
-----
from app.audit.pdf_report import generate_audit_pdf

# Example minimal payload (fields are optional; sensible defaults/placeholder are applied):
audit_data = {
    "website_url": "https://example.com",
    "audit_datetime": "2026-02-10 12:34",
    "report_id": "ABC123",
    "brand": {"generated_by": "Your SaaS Brand", "logo_path": None},
    "scores": {
        "overall": 78,
        "performance": 72,
        "seo": 81,
        "security": 66,
        "accessibility": 75,
        "best_practices": 70,
        "professional_touch": 80,
    },
    "summary": {
        "traffic_impact": "High impact issues detected",
        "risk_level": "Medium"  # "Low" | "Medium" | "High"
    },
    "priority_actions": [
        "Reduce LCP images with AVIF/WebP + proper dimensions",
        "Implement HSTS and add missing security headers",
        "Fix duplicate H1 and add unique meta descriptions"
    ],
    "performance": {
        "ttfb": "650 ms",
        "fully_loaded": "3.2 s",
        "page_size": "1.9 MB",
        "total_requests": 72,
        "critical_rendering_path": "TBD",
        "resource_optimization": "TBD",
        "js_file_count": 21,
        "css_file_count": 7,
        "image_formats": "Mixed (PNG/JPG), few WebP",
        "lazy_loading": "Partial",
        "minification": "JS=Yes, CSS=Partial, HTML=No",
        "mobile": {
            "mobile_friendly": "Yes",
            "viewport_meta": "Present",
            "responsive_layout": "Pass"
        }
    },
    "seo": {
        "onpage": {
            "title_status": "Length OK; no duplicates found",
            "meta_description": "Missing on 3 pages",
            "canonical": "Present",
            "headings": "Multiple H1 on 2 pages",
            "broken_links": "2 internal 404s, 1 external 404"
        },
        "indexing": {
            "robots_txt": "Present",
            "meta_robots": "Noindex on 1 page",
            "xml_sitemap": "Present",
            "crawl_depth": "3 levels typical",
            "http_status": "Mixed (200/301/404)"
        },
        "content_quality": {
            "word_count": "Avg ~800/page",
            "keyword_density": "Natural; no stuffing detected",
            "duplicate_risk": "Low",
            "image_alts": "Missing on ~12%"
        }
    },
    "security": {
        "transport_headers": {
            "https_enforced": "Yes",
            "ssl_validity": "Valid until 2026-12-01",
            "hsts": "Not set",
            "csp": "Missing",
            "x_frame_options": "SAMEORIGIN",
            "x_content_type_options": "nosniff",
            "referrer_policy": "strict-origin-when-cross-origin"
        },
        "vulnerabilities": {
            "mixed_content": "None detected",
            "open_directories": "None detected",
            "outdated_libs": "1 JS library outdated (jQuery 3.3)"
        },
        "compliance": {
            "pci_dss": "N/A (no card pages visible)",
            "gdpr": "Cookie banner present; no granular controls"
        }
    },
    "accessibility": {
        "mandatory": {
            "alt_text": "Missing on ~12% images",
            "color_contrast": "Needs review on buttons",
            "font_readability": "OK (>= 16px body)",
            "keyboard_navigation": "Focus outlines present",
            "aria_labels": "Partial coverage on icons"
        },
        "levels": {"A": "Pass", "AA": "Partial", "AAA": "Not evaluated"}
    },
    "best_practices_ux": {
        "code_quality": {"html_validation": "Minor warnings", "deprecated_tags": "None", "inline_usage": "Limited"},
        "ux_signals": {"cta_visibility": "Strong", "navigation": "Clear", "broken_ui": "None observed", "above_fold": "Value prop visible"},
        "trust_signals": {"contact_info": "Visible", "privacy_policy": "Present", "terms": "Present", "social_proof": "Logos + reviews"}
    },
    "competitors": {
        "names": ["competitor-a.com", "competitor-b.com", "competitor-c.com"],
        "metrics": {  # put numbers/strings as available; display is robust
            "Speed (s)": ["3.2", "2.7", "3.6", "2.4"],
            "SEO Score (0–100)": ["81", "78", "84", "76"],
            "Mobile Score (0–100)": ["74", "70", "79", "67"],
            "Domain Authority (0–100)": ["45", "52", "61", "38"],
            "Market Position (rank)": ["3", "4", "2", "5"]
        }
    },
    "analytics": {
        "google_analytics": "Detected (GA4)",
        "gtm": "Present",
        "facebook_pixel": "Not detected",
        "conversion_ready": "Partial (missing thank-you goal)",
        "event_issues": "Scroll depth events double-firing"
    },
    "ai_insights": {
        "findings": [
            "High JS usage affecting speed",
            "Missing canonical on a few paginated URLs may cause SEO duplication",
            "Large hero images detected above the fold"
        ],
        "predictive_risk": {
            "seo_traffic_loss": "Medium",
            "performance_impact": "TTFB and LCP likely harming conversions by 3–8%"
        }
    },
    "actions": [
        {"priority": "Quick Win", "category": "Performance", "issue": "Uncompressed hero images", "impact": "High", "recommendation": "Serve AVIF/WebP + width/height attrs"},
        {"priority": "Quick Win", "category": "SEO", "issue": "Duplicate H1", "impact": "Medium", "recommendation": "Restrict to single H1, use H2 for sections"},
        {"priority": "Strategic", "category": "Security", "issue": "No HSTS + missing CSP", "impact": "High", "recommendation": "Enable HSTS, add strict CSP"},
        {"priority": "Strategic", "category": "Accessibility", "issue": "Low contrast on CTA", "impact": "High", "recommendation": "Meet WCAG AA contrast"}
    ],
    "metadata": {
        "tool_version": "1.2.0",
        "audit_engine": "Hybrid ruleset + manual verification",
        "methodology": "Core Web Vitals, WCAG 2.1, OWASP Top 10, sitemaps/robots, on-page heuristics",
        "disclaimer": "Findings require validation on staging before production changes."
    }
}

# Get bytes (for web response) or write to a file
pdf_bytes = generate_audit_pdf(audit_data)  # returns bytes
with open("website-audit.pdf", "wb") as f:
    f.write(pdf_bytes)

"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# -----------------------------
# Fonts & Helpers
# -----------------------------

def _register_base_font() -> str:
    """
    Try to register a Unicode-capable sans font (DejaVuSans) for emoji and symbols.
    Fallback to Helvetica if not available.
    """
    try:
        pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        return "DejaVuSans"
    except Exception:
        return "Helvetica"


BASE_FONT = _register_base_font()


class ScoreBar(Flowable):
    """
    A horizontal score bar from 0..100 with color mapping:
    - green for >= 85
    - yellow for >= 60
    - red otherwise
    """

    def __init__(self, score: Union[int, float], width: float = 150, height: float = 10, label: str = ""):
        super().__init__()
        clamped = 0 if score is None else max(0, min(100, float(score)))
        self.score = clamped
        self.width = width
        self.height = height
        self.label = label

    def draw(self):
        c = self.canv
        c.setStrokeColor(colors.grey)
        c.rect(0, 0, self.width, self.height, stroke=1, fill=0)

        if self.score >= 85:
            fill = colors.Color(0.16, 0.75, 0.38)  # green
        elif self.score >= 60:
            fill = colors.Color(0.98, 0.78, 0.2)   # yellow
        else:
            fill = colors.Color(0.91, 0.3, 0.24)   # red

        c.setFillColor(fill)
        c.rect(0, 0, self.width * (self.score / 100.0), self.height, stroke=0, fill=1)

        if self.label:
            c.setFillColor(colors.black)
            c.setFont(BASE_FONT, 8)
            c.drawString(self.width + 6, 1, f"{self.label}: {int(round(self.score))}")


def _p_style_sheet() -> Dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBig", fontName=BASE_FONT, fontSize=20, leading=24,
                              alignment=TA_LEFT, spaceAfter=8))
    styles.add(ParagraphStyle(name="H1", fontName=BASE_FONT, fontSize=16, leading=20,
                              spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="H2", fontName=BASE_FONT, fontSize=13, leading=17,
                              spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="Body", fontName=BASE_FONT, fontSize=10.5, leading=14))
    styles.add(ParagraphStyle(name="Small", fontName=BASE_FONT, fontSize=9, leading=12))
    return styles


def _risk_emoji(level: str) -> str:
    level = (level or "").strip().lower()
    if level == "low":
        return "🟢 Low"
    if level == "medium":
        return "🟡 Medium"
    if level == "high":
        return "🔴 High"
    return "TBD"


def _safe(audit: Dict[str, Any], key: str, default: Any = "TBD") -> Any:
    v = audit.get(key, default)
    return default if v in (None, "") else v


def _safe_get(dct: Optional[Dict[str, Any]], path: Iterable[str], default: Any = "TBD") -> Any:
    cur: Any = dct or {}
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return default if cur in (None, "") else cur


def _meta_datetime(audit: Dict[str, Any]) -> str:
    dt = _safe(audit, "audit_datetime", None)
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt or datetime.now().strftime("%Y-%m-%d %H:%M")


def _overall_from_categories(scores: Dict[str, Union[int, float]]) -> Optional[int]:
    """
    Compute overall average from categories if 'overall' missing.
    """
    if not scores:
        return None
    categories = [
        scores.get("performance"),
        scores.get("seo"),
        scores.get("security"),
        scores.get("accessibility"),
        scores.get("best_practices"),
        scores.get("professional_touch"),
    ]
    nums = [float(x) for x in categories if isinstance(x, (int, float))]
    if not nums:
        return None
    return int(round(sum(nums) / len(nums)))


# -----------------------------
# Builders for Sections
# -----------------------------

def _build_meta_header(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    story: List[Any] = []
    title = "International-Standard Website Audit Report"
    story.append(Paragraph(title, styles["TitleBig"]))

    website = _safe(audit, "website_url", "TBD — Provide URL")
    dt_str = _meta_datetime(audit)
    report_id = _safe(_safe(audit, "report_id", None) or {}, "report_id", "").strip()
    brand = audit.get("brand", {}) or {}
    generated_by = brand.get("generated_by", "Your SaaS Brand")
    logo_path = brand.get("logo_path")

    # Optional logo (small)
    if logo_path:
        try:
            img = Image(logo_path, width=22 * mm, height=22 * mm)
            story.append(img)
            story.append(Spacer(1, 4))
        except Exception:
            pass  # ignore logo errors; continue

    meta_table = Table(
        [
            ["Website URL", website],
            ["Audit date & time", dt_str],
            ["Report ID", _safe(audit, "report_id", "Auto")],
            ["Generated by", generated_by],
        ],
        colWidths=[45 * mm, 120 * mm],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 6))
    return story


def _build_executive_summary(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    story: List[Any] = [Paragraph("1️⃣ Executive Summary", styles["H1"])]

    scores = audit.get("scores", {}) or {}
    if "overall" not in scores or scores.get("overall") in (None, ""):
        overall = _overall_from_categories(scores)
        if overall is not None:
            scores["overall"] = overall

    ordered = [
        ("Overall Health Score", scores.get("overall", 0)),
        ("Performance", scores.get("performance", 0)),
        ("SEO", scores.get("seo", 0)),
        ("Security", scores.get("security", 0)),
        ("Accessibility", scores.get("accessibility", 0)),
        ("Best Practices", scores.get("best_practices", 0)),
        ("Professional Touch", scores.get("professional_touch", 0)),
    ]
    score_rows = [[k, ScoreBar(v, width=70, height=8, label=str(int(round(v)) if v else 0))] for k, v in ordered]
    score_table = Table(score_rows, colWidths=[60 * mm, 95 * mm])
    score_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONT", (0, 0), (0, -1), BASE_FONT, 10.5),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.black),
            ]
        )
    )

    traffic_impact = _safe_get(audit.get("summary"), ["traffic_impact"], "High impact issues detected")
    risk_level = _safe_get(audit.get("summary"), ["risk_level"], "TBD")
    risk_line = f"{_risk_emoji(risk_level)}"

    summary_tbl = Table(
        [
            ["Traffic-impact summary", traffic_impact],
            ["Risk level", risk_line],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    summary_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    actions = audit.get("priority_actions", []) or []
    if actions:
        bullet = "  ".join([f"{i+1}) {a}" for i, a in enumerate(actions[:5])])
    else:
        bullet = "1) TBD  2) TBD  3) TBD  4) (optional)  5) (optional)"
    priority_actions = Table([["Priority Actions (3–5)", bullet]], colWidths=[60 * mm, 95 * mm])
    priority_actions.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    story.extend([score_table, Spacer(1, 6), summary_tbl, Spacer(1, 6), priority_actions, PageBreak()])
    return story


def _build_performance(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    p = audit.get("performance", {}) or {}
    m = p.get("mobile", {}) or {}

    rows = [
        ["2️⃣ Technical Performance Audit (CORE)", ""],
        ["Page Load & Speed", ""],
        ["Time to First Byte (TTFB)", p.get("ttfb", "TBD")],
        ["Fully Loaded Time", p.get("fully_loaded", "TBD")],
        ["Page Size (KB/MB)", p.get("page_size", "TBD")],
        ["Total Requests", p.get("total_requests", "TBD")],
        ["Critical Rendering Path", p.get("critical_rendering_path", "TBD")],
        ["Resource Optimization", p.get("resource_optimization", "TBD")],
        ["JS file count", p.get("js_file_count", "TBD")],
        ["CSS file count", p.get("css_file_count", "TBD")],
        ["Image size & formats", p.get("image_formats", "TBD")],
        ["Lazy loading status", p.get("lazy_loading", "TBD")],
        ["Minification (JS/CSS/HTML)", p.get("minification", "TBD")],
        ["Mobile Performance", ""],
        ["Mobile friendliness", m.get("mobile_friendly", "TBD")],
        ["Viewport meta tag", m.get("viewport_meta", "TBD")],
        ["Responsive layout check", m.get("responsive_layout", "TBD")],
        ["Benchmarks", "Green: < 2.5s | Warning: 2.5–4s | Critical: > 4s"],
    ]

    story: List[Any] = []
    # Heading as styled H1, not table
    story.append(Paragraph(rows[0][0], styles["H1"]))
    perf_tbl = Table(rows[1:], colWidths=[60 * mm, 95 * mm])
    perf_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    story.extend([perf_tbl, PageBreak()])
    return story


def _build_seo(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    seo = audit.get("seo", {}) or {}
    onpage = seo.get("onpage", {}) or {}
    indexing = seo.get("indexing", {}) or {}
    content = seo.get("content_quality", {}) or seo.get("content", {}) or {}

    story: List[Any] = [Paragraph("3️⃣ SEO Audit (CORE)", styles["H1"])]

    seo_onpage = Table(
        [
            ["On-Page SEO", ""],
            ["Page title (length + duplication)", onpage.get("title_status", "TBD")],
            ["Meta description (presence & length)", onpage.get("meta_description", "TBD")],
            ["Canonical URL", onpage.get("canonical", "TBD")],
            ["H1/H2 structure", onpage.get("headings", "TBD")],
            ["Broken links (internal / external)", onpage.get("broken_links", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    seo_onpage.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    seo_indexing = Table(
        [
            ["Indexing & Crawlability", ""],
            ["Robots.txt", indexing.get("robots_txt", "TBD")],
            ["Meta robots tags", indexing.get("meta_robots", "TBD")],
            ["XML sitemap presence", indexing.get("xml_sitemap", "TBD")],
            ["Crawl depth", indexing.get("crawl_depth", "TBD")],
            ["HTTP status codes", indexing.get("http_status", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    seo_indexing.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    seo_content = Table(
        [
            ["Content Quality", ""],
            ["Word count", content.get("word_count", "TBD")],
            ["Keyword usage density (basic)", content.get("keyword_density", "TBD")],
            ["Duplicate content risk", content.get("duplicate_risk", "TBD")],
            ["Image alt attributes", content.get("image_alts", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    seo_content.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    story.extend([seo_onpage, Spacer(1, 6), seo_indexing, Spacer(1, 6), seo_content, PageBreak()])
    return story


def _build_security(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    sec = audit.get("security", {}) or {}
    th = sec.get("transport_headers", {}) or {}
    vuln = sec.get("vulnerabilities", {}) or {}
    comp = sec.get("compliance", {}) or {}

    story: List[Any] = [Paragraph("4️⃣ Security Audit (MANDATORY)", styles["H1"])]

    sec_transport = Table(
        [
            ["Transport & Headers", ""],
            ["HTTPS enforced", th.get("https_enforced", "TBD")],
            ["SSL certificate validity", th.get("ssl_validity", "TBD")],
            ["HSTS", th.get("hsts", "TBD")],
            ["CSP", th.get("csp", "TBD")],
            ["X-Frame-Options", th.get("x_frame_options", "TBD")],
            ["X-Content-Type-Options", th.get("x_content_type_options", "TBD")],
            ["Referrer-Policy", th.get("referrer_policy", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    sec_transport.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    sec_vuln = Table(
        [
            ["Vulnerabilities (Light Scan)", ""],
            ["Mixed content", vuln.get("mixed_content", "TBD")],
            ["Open directories", vuln.get("open_directories", "TBD")],
            ["Outdated libraries (basic detection)", vuln.get("outdated_libs", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    sec_vuln.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    sec_comp = Table(
        [
            ["Compliance Flags", ""],
            ["PCI-DSS (basic)", comp.get("pci_dss", "TBD")],
            ["GDPR readiness (cookie hints)", comp.get("gdpr", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    sec_comp.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    story.extend([sec_transport, Spacer(1, 6), sec_vuln, Spacer(1, 6), sec_comp, PageBreak()])
    return story


def _build_accessibility(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    acc = audit.get("accessibility", {}) or {}
    mand = acc.get("mandatory", {}) or {}
    levels = acc.get("levels", {}) or {}

    story: List[Any] = [Paragraph("5️⃣ Accessibility Audit (WCAG 2.1)", styles["H1"])]

    acc_mand = Table(
        [
            ["Mandatory Checks", ""],
            ["Image ALT text", mand.get("alt_text", "TBD")],
            ["Color contrast", mand.get("color_contrast", "TBD")],
            ["Font readability", mand.get("font_readability", "TBD")],
            ["Keyboard navigation", mand.get("keyboard_navigation", "TBD")],
            ["ARIA labels", mand.get("aria_labels", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    acc_mand.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    acc_levels = Table(
        [
            ["Compliance Levels", ""],
            ["WCAG A", levels.get("A", "TBD")],
            ["WCAG AA", levels.get("AA", "TBD")],
            ["WCAG AAA (optional)", levels.get("AAA", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    acc_levels.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    story.extend([acc_mand, Spacer(1, 6), acc_levels, PageBreak()])
    return story


def _build_best_practices_ux(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    b = audit.get("best_practices_ux", {}) or {}
    cq = b.get("code_quality", {}) or {}
    ux = b.get("ux_signals", {}) or {}
    trust = b.get("trust_signals", {}) or {}

    story: List[Any] = [Paragraph("6️⃣ Best Practices & UX", styles["H1"])]

    code_quality = Table(
        [
            ["Code Quality", ""],
            ["HTML validation", cq.get("html_validation", "TBD")],
            ["Deprecated tags", cq.get("deprecated_tags", "TBD")],
            ["Inline styles/scripts", cq.get("inline_usage", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    code_quality.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    ux_signals = Table(
        [
            ["UX Signals", ""],
            ["CTA visibility", ux.get("cta_visibility", "TBD")],
            ["Navigation clarity", ux.get("navigation", "TBD")],
            ["Broken UI elements", ux.get("broken_ui", "TBD")],
            ["Above-the-fold clarity", ux.get("above_fold", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    ux_signals.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    trust_signals = Table(
        [
            ["Trust Signals", ""],
            ["Contact info", trust.get("contact_info", "TBD")],
            ["Privacy policy", trust.get("privacy_policy", "TBD")],
            ["Terms & conditions", trust.get("terms", "TBD")],
            ["Social proof indicators", trust.get("social_proof", "TBD")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    trust_signals.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )

    story.extend([code_quality, Spacer(1, 6), ux_signals, Spacer(1, 6), trust_signals, PageBreak()])
    return story


def _build_competitors(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    comp = audit.get("competitors", {}) or {}
    names: List[str] = comp.get("names", []) or []
    target = _safe(audit, "website_url", "Target")
    header = ["Metric", "Target Site"] + ([*names] if names else ["Competitor A", "Competitor B", "Competitor C"])

    metrics: Dict[str, List[Any]] = comp.get("metrics", {}) or {}
    rows: List[List[Any]] = [header]
    for metric_name, values in metrics.items():
        # values should align length with header; pad/truncate
        vals = list(values or [])
        total_cols = len(header) - 1  # not counting metric col
        if len(vals) < total_cols:
            vals = vals + ["TBD"] * (total_cols - len(vals))
        if len(vals) > total_cols:
            vals = vals[:total_cols]
        rows.append([metric_name, *vals])

    # If no metrics provided, add placeholders
    if len(rows) == 1:
        rows.extend([
            ["Speed (s)", "TBD", "TBD", "TBD", "TBD"],
            ["SEO Score (0–100)", "TBD", "TBD", "TBD", "TBD"],
            ["Mobile Score (0–100)", "TBD", "TBD", "TBD", "TBD"],
            ["Domain Authority (0–100)", "TBD", "TBD", "TBD", "TBD"],
            ["Market Position (rank)", "TBD", "TBD", "TBD", "TBD"],
        ])

    story: List[Any] = [Paragraph("7️⃣ Competitor Benchmarking (PREMIUM)", styles["H1"])]
    comp_tbl = Table(rows, colWidths=[40 * mm] + [23 * mm] * (len(rows[0]) - 1))
    comp_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 9.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    story.extend([comp_tbl, PageBreak()])
    return story


def _build_analytics(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    a = audit.get("analytics", {}) or {}

    story: List[Any] = [Paragraph("8️⃣ Analytics & Tracking", styles["H1"])]
    anal_tbl = Table(
        [
            ["Google Analytics detected", a.get("google_analytics", "TBD")],
            ["Google Tag Manager", a.get("gtm", "TBD")],
            ["Facebook Pixel", a.get("facebook_pixel", "TBD")],
            ["Conversion tracking readiness", a.get("conversion_ready", "TBD")],
            ["Event tracking issues", a.get("event_issues", "TBD")],
        ],
        colWidths=[80 * mm, 75 * mm],
    )
    anal_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    story.extend([anal_tbl, PageBreak()])
    return story


def _build_ai_insights(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    ai = audit.get("ai_insights", {}) or {}
    findings: List[str] = ai.get("findings", []) or []
    predictive = ai.get("predictive_risk", {}) or {}

    story: List[Any] = [Paragraph("9️⃣ AI-Driven Insights (ENTERPRISE)", styles["H1"])]

    af = "\n".join([f"• {f}" for f in findings]) if findings else (
        "“High JS usage affecting speed” (example)\n"
        "“Missing canonical may cause SEO duplication” (example)\n"
        "“Large images detected above the fold” (example)"
    )
    pr = (
        f"SEO traffic loss risk: {predictive.get('seo_traffic_loss', 'TBD')}\n"
        f"Performance impact estimation: {predictive.get('performance_impact', 'TBD')}"
    )

    ai_tbl = Table(
        [
            ["Automated Findings", af],
            ["Predictive Risk", pr],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    ai_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    story.extend([ai_tbl, PageBreak()])
    return story


def _build_actions(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    actions: List[Dict[str, Any]] = audit.get("actions", []) or []

    story: List[Any] = [Paragraph("🔟 Prioritized Action Plan (MANDATORY)", styles["H1"])]

    rows: List[List[Any]] = [["Priority", "Category", "Issue", "Impact", "Recommendation"]]
    if not actions:
        rows.extend([
            ["Quick Win", "Performance", "TBD", "High / Medium / Low", "TBD"],
            ["Quick Win", "SEO", "TBD", "High / Medium / Low", "TBD"],
            ["Strategic", "Security", "TBD", "High / Medium / Low", "TBD"],
            ["Strategic", "Accessibility", "TBD", "High / Medium / Low", "TBD"],
        ])
    else:
        for a in actions:
            rows.append([
                a.get("priority", "TBD"),
                a.get("category", "TBD"),
                a.get("issue", "TBD"),
                a.get("impact", "TBD"),
                a.get("recommendation", "TBD"),
            ])

    action_tbl = Table(rows, colWidths=[25 * mm, 30 * mm, 40 * mm, 25 * mm, 35 * mm])
    action_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 9.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    story.extend([action_tbl, PageBreak()])
    return story


def _build_compliance(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    story: List[Any] = [Paragraph("1️⃣1️⃣ Compliance & Standards Reference (PRO)", styles["H1"])]
    refs = [
        "WCAG 2.1 (W3C) — Accessibility standards",
        "Google Page Experience & Core Web Vitals — Performance/UX",
        "OWASP Top 10 (light reference) — Web security risks",
        "ISO/IEC 27001 (reference only) — Information security management",
    ]
    ref_list = "\n".join([f"- {r}" for r in refs])
    story.append(Paragraph(ref_list, styles["Body"]))
    story.append(PageBreak())
    return story


def _build_metadata(audit: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> List[Any]:
    meta = audit.get("metadata", {}) or {}
    story: List[Any] = [Paragraph("1️⃣2️⃣ Audit Metadata (PRO)", styles["H1"])]

    meta2_tbl = Table(
        [
            ["Tool version", meta.get("tool_version", "1.0.0")],
            ["Audit engine", meta.get("audit_engine", "Hybrid ruleset + manual verification")],
            ["Methodology summary", meta.get("methodology", "Core Web Vitals, WCAG 2.1, OWASP Top 10, sitemap/robots, and heuristics.")],
            ["Disclaimer", meta.get("disclaimer", "Populate with verified data before client delivery.")],
            ["Report ID", _safe(audit, "report_id", "Auto")],
            ["Generated by", (audit.get("brand") or {}).get("generated_by", "Your SaaS Brand")],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    meta2_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    story.extend([meta2_tbl])

    story.append(Spacer(1, 10))
    sell_tbl = Table(
        [
            ["What Makes It SELLABLE", ""],
            ["Executive summary", "⭐⭐⭐⭐⭐"],
            ["Prioritized actions", "⭐⭐⭐⭐⭐"],
            ["AI insights", "⭐⭐⭐⭐"],
            ["Competitor comparison", "⭐⭐⭐⭐"],
            ["Compliance references", "⭐⭐⭐⭐"],
            ["Clean charts & visuals", "⭐⭐⭐⭐⭐"],
        ],
        colWidths=[60 * mm, 95 * mm],
    )
    sell_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), BASE_FONT, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    story.append(sell_tbl)
    return story


# -----------------------------
# Public API
# -----------------------------

def generate_audit_pdf(audit: Dict[str, Any]) -> bytes:
    """
    Generate the International-Standard Website Audit PDF.

    Parameters
    ----------
    audit : dict
        Structured data payload (see module docstring for example).

    Returns
    -------
    bytes
        The PDF binary content (ready to stream as HTTP response or to write to disk).
    """
    styles = _p_style_sheet()

    # Prepare a BytesIO buffer (Railway/web-friendly)
    buff = BytesIO()
    doc = SimpleDocTemplate(
        buff,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="International-Standard Website Audit",
        author=(audit.get("brand") or {}).get("generated_by", "Your SaaS Brand"),
        subject=_safe(audit, "website_url", "Website Audit"),
        keywords=["Website Audit", "SEO", "Performance", "Security", "Accessibility", "Core Web Vitals", "WCAG", "OWASP"],
    )

    story: List[Any] = []
    story.extend(_build_meta_header(audit, styles))
    story.extend(_build_executive_summary(audit, styles))
    story.extend(_build_performance(audit, styles))
    story.extend(_build_seo(audit, styles))
    story.extend(_build_security(audit, styles))
    story.extend(_build_accessibility(audit, styles))
    story.extend(_build_best_practices_ux(audit, styles))
    story.extend(_build_competitors(audit, styles))
    story.extend(_build_analytics(audit, styles))
    story.extend(_build_ai_insights(audit, styles))
    story.extend(_build_actions(audit, styles))
    story.extend(_build_compliance(audit, styles))
    story.extend(_build_metadata(audit, styles))

    doc.build(story)
    pdf_bytes = buff.getvalue()
    buff.close()
    return pdf_bytes


# -----------------------------
# CLI / Local test
# -----------------------------
if __name__ == "__main__":
    # Minimal smoke test to produce a sample PDF locally
    sample = {
        "website_url": "https://example.com",
        "audit_datetime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "report_id": "SAMPLE-" + datetime.now().strftime("%H%M%S"),
        "brand": {"generated_by": "Your SaaS Brand", "logo_path": None},
        "scores": {"performance": 70, "seo": 82, "security": 65, "accessibility": 74, "best_practices": 68, "professional_touch": 80},
        "summary": {"traffic_impact": "High impact issues detected", "risk_level": "Medium"},
        "priority_actions": ["Compress hero images", "Enable HSTS + CSP", "Fix duplicate H1 tags"],
        "metadata": {"tool_version": "1.2.0", "audit_engine": "Hybrid", "methodology": "Industry best practices", "disclaimer": "Template output for testing"},
    }
    out = generate_audit_pdf(sample)
    with open("International-Standard-Website-Audit-SAMPLE.pdf", "wb") as fp:
        fp.write(out)
    print("Sample PDF written: International-Standard-Website-Audit-SAMPLE.pdf")
