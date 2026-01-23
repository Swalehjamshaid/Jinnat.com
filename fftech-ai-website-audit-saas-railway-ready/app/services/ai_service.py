
# app/services/ai_service.py
import logging
from typing import Dict, Any

logger = logging.getLogger("AIService")


class AIService:
    """
    Offline AI summary generator.

    This class intentionally avoids any external API calls and produces a concise,
    deterministic summary based solely on the provided audit_data.
    The public interface is preserved to avoid changing existing call sites.
    """

    def __init__(self) -> None:
        logger.info("AIService initialized in OFFLINE mode (no external APIs).")

    async def generate_audit_summary(self, audit_data: Dict[str, Any]) -> str:
        """
        Produce a human-readable summary without external network calls.
        Expects audit_data with keys:
          - url: str
          - score: float (0..100)
          - performance: Optional[Dict[str, str]] with 'fcp', 'lcp', 'cls'
          - connectivity: Dict[str, Any] with 'status' and 'detail'
        """
        try:
            url = audit_data.get("url", "N/A")
            score = float(audit_data.get("score", 0.0))
            perf = audit_data.get("performance") or {}
            conn = audit_data.get("connectivity") or {}

            fcp = perf.get("fcp", "N/A")
            lcp = perf.get("lcp", "N/A")
            cls = perf.get("cls", "N/A")
            c_status = conn.get("status", "UNKNOWN")
            c_detail = conn.get("detail", "N/A")

            # Simple rule-based insights (offline)
            recs = []
            if score < 60:
                tier = "Poor"
                recs += [
                    "Reduce Time to First Byte (TTFB) by enabling caching/CDN and optimizing backend.",
                    "Minimize render‑blocking resources: inline critical CSS and defer non‑critical JS.",
                    "Compress and properly size images; adopt next‑gen formats (WebP/AVIF).",
                    "Audit third‑party scripts; remove or lazy‑load nonessential tags.",
                ]
            elif score < 85:
                tier = "Needs Improvement"
                recs += [
                    "Trim unused JavaScript and CSS; split bundles and enable HTTP/2.",
                    "Improve image loading strategy (responsive sizes, lazy‑load offscreen media).",
                    "Establish performance budgets and monitor in CI to prevent regressions.",
                ]
            else:
                tier = "Good"
                recs += [
                    "Maintain current performance; lock budgets and track with automated checks.",
                    "Periodically review third‑party scripts to keep payloads lean.",
                ]

            # Connectivity awareness
            if c_status == "WARNING":
                recs.append("Resolve SSL configuration issues; currently bypassed SSL was required.")
            elif c_status == "FAILURE":
                recs.append("Site reachability failed. Verify DNS, firewall, or uptime before retesting.")

            lines = [
                f"Audit Summary (Offline) for {url}",
                f"Overall Score: {score:.2f} / 100 ({tier})",
                f"Connectivity: {c_status} ({c_detail})",
                "Key Metrics (estimated):",
                f"- FCP: {fcp}",
                f"- LCP: {lcp}",
                f"- CLS: {cls}",
                "Recommendations:",
            ]
            lines += [f"• {r}" for r in recs]

            return "\n".join(lines)
        except Exception as e:
            logger.exception("Offline AI summary failed: %s", e)
            # Always return a safe string (never raise up the stack)
            return "Summary unavailable due to an internal error. Please re-run the audit."
``
