
# app/services/ai_service.py
import logging
from typing import Dict, Any

logger = logging.getLogger("AIService")


class AIService:
    """
    Offline AI summary generator (no external API calls).
    Produces a clear, actionable summary from the audit report.
    """

    def __init__(self) -> None:
        logger.info("AIService initialized in OFFLINE mode (no external APIs).")

    async def generate_audit_summary(self, audit_data: Dict[str, Any]) -> str:
        """
        Expects audit_data with:
          - url: str
          - score: float 0..100
          - category_scores: dict (performance, ux, connectivity, security)
          - performance: dict with 'fcp', 'lcp', 'cls' (strings, estimated)
          - connectivity: dict with 'status', 'detail'
        """
        try:
            url = audit_data.get("url", "N/A")
            score = float(audit_data.get("score", 0.0))
            categories = audit_data.get("category_scores") or {}
            perf = audit_data.get("performance") or {}
            conn = audit_data.get("connectivity") or {}

            perf_pct = categories.get("performance", 0.0)
            ux_pct = categories.get("ux", 0.0)
            con_pct = categories.get("connectivity", 0.0)
            sec_pct = categories.get("security", 0.0)

            lines = [
                f"Executive Summary (Offline) for {url}",
                f"Health Index: {score:.2f} / 100",
                "Category Highlights:",
                f"- Performance: {perf_pct:.1f}%",
                f"- UX: {ux_pct:.1f}%",
                f"- Connectivity: {con_pct:.1f}%",
                f"- Security: {sec_pct:.1f}%",
                "Key Metrics (estimated):",
                f"- FCP: {perf.get('fcp', 'N/A')}",
                f"- LCP: {perf.get('lcp', 'N/A')}",
                f"- CLS: {perf.get('cls', 'N/A')}",
                f"Connectivity: {conn.get('status', 'UNKNOWN')} ({conn.get('detail', 'N/A')})",
                "Recommendations:",
            ]

            # Tiered recommendations
            if score < 60:
                lines += [
                    "• Improve TTFB with caching/CDN and backend optimizations.",
                    "• Reduce render‑blocking JS/CSS; inline critical CSS, defer non-essential JS.",
                    "• Compress/resize images; adopt WebP/AVIF with lazy‑loading.",
                    "• Address SSL issues and add HSTS/CSP security headers.",
                ]
            elif score < 85:
                lines += [
                    "• Trim unused JS/CSS and split bundles; leverage HTTP/2.",
                    "• Optimize image delivery and establish performance budgets.",
                    "• Review security headers and enforce stricter policies.",
                ]
            else:
                lines += [
                    "• Maintain current performance; enforce budgets in CI.",
                    "• Routinely review third‑party scripts and headers.",
                ]

            return "\n".join(lines)
        except Exception as e:
            logger.exception("Offline AI summary failed: %s", e)
            return "Summary unavailable due to an internal error. Please re-run the audit."
