def calculate_performance_score(lcp_ms: int) -> int:
    """
    World-class performance scoring engine.

    INPUT (UNCHANGED):
        lcp_ms: int  → Largest Contentful Paint in milliseconds

    OUTPUT (UNCHANGED):
        int → Performance score (0–100)

    INTERNAL METRICS (industry-aligned, simulated safely):
        - LCP (Core Web Vitals – primary signal)
        - FCP (First Contentful Paint)
        - TTFB (Time to First Byte)
        - CLS (Cumulative Layout Shift)
        - Lighthouse-style weighted scoring

    NOTE:
        Only LCP is passed in externally.
        Other metrics are inferred conservatively to avoid false positives.
    """

    # ────────────────────────────────────────────────
    # 1️⃣ Defensive validation (enterprise-grade)
    # ────────────────────────────────────────────────
    if not isinstance(lcp_ms, (int, float)) or lcp_ms <= 0:
        return 0

    lcp_ms = int(lcp_ms)

    # ────────────────────────────────────────────────
    # 2️⃣ Simulated auxiliary metrics (SAFE inference)
    #    These NEVER override LCP dominance
    # ────────────────────────────────────────────────

    # Industry-backed realistic ratios
    fcp_ms = int(lcp_ms * 0.6)      # FCP usually ~50–70% of LCP
    ttfb_ms = int(lcp_ms * 0.25)    # TTFB ~20–30% of LCP
    cls = 0.05 if lcp_ms <= 2500 else 0.15 if lcp_ms <= 4000 else 0.25

    # ────────────────────────────────────────────────
    # 3️⃣ Individual metric scoring (0–100)
    # ────────────────────────────────────────────────

    def score_lcp(ms: int) -> int:
        if ms <= 1000: return 100
        if ms <= 1500: return 95
        if ms <= 2000: return 90
        if ms <= 2500: return 85  # Google "Good"
        if ms <= 3000: return 75
        if ms <= 3500: return 65
        if ms <= 4000: return 55  # Needs improvement
        if ms <= 5000: return 40
        if ms <= 6000: return 30
        return 20

    def score_fcp(ms: int) -> int:
        if ms <= 1000: return 100
        if ms <= 1800: return 85
        if ms <= 3000: return 65
        return 40

    def score_ttfb(ms: int) -> int:
        if ms <= 200: return 100
        if ms <= 500: return 85
        if ms <= 800: return 65
        return 40

    def score_cls(value: float) -> int:
        if value <= 0.1: return 100
        if value <= 0.25: return 70
        return 40

    lcp_score = score_lcp(lcp_ms)
    fcp_score = score_fcp(fcp_ms)
    ttfb_score = score_ttfb(ttfb_ms)
    cls_score = score_cls(cls)

    # ────────────────────────────────────────────────
    # 4️⃣ Lighthouse-style weighted aggregation
    #    (Google-inspired weighting)
    # ────────────────────────────────────────────────
    final_score = int(
        (lcp_score * 0.45) +     # LCP dominates
        (fcp_score * 0.20) +
        (ttfb_score * 0.20) +
        (cls_score * 0.15)
    )

    # ────────────────────────────────────────────────
    # 5️⃣ Clamp & return (contract preserved)
    # ────────────────────────────────────────────────
    return max(0, min(100, final_score))
