def analyze_performance(url: str) -> Dict[str, Any]:
    # ... existing code ...

    if settings.PSI_API_KEY:
        try:
            desktop_result = fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="desktop")
            mobile_result = fetch_lighthouse(url, api_key=settings.PSI_API_KEY, strategy="mobile")

            # NEW: Check for this specific Lighthouse failure
            if "error" in desktop_result and "FAILED_DOCUMENT_REQUEST" in str(desktop_result.get("error", "")):
                print(f"[PSI] FAILED_DOCUMENT_REQUEST detected for {url} (desktop)")
                desktop_result = {}
            if "error" in mobile_result and "FAILED_DOCUMENT_REQUEST" in str(mobile_result.get("error", "")):
                print(f"[PSI] FAILED_DOCUMENT_REQUEST detected for {url} (mobile)")
                mobile_result = {}

        except Exception as e:
            print(f"[Performance] PSI fetch failed: {e}")
            desktop_result = mobile_result = {}

    # Prefer desktop
    if desktop_result and desktop_result.get("lcp_ms"):  # check if meaningful data
        desktop_result["fallback_active"] = False
        return desktop_result

    if mobile_result and mobile_result.get("lcp_ms"):
        mobile_result["fallback_active"] = False
        return mobile_result

    # Fallback (already good)
    # ... your existing requests fallback code ...

    # NEW: Add note about PSI failure
    fallback_result = {
        # ... your fallback dict ...
        "psi_failed": True,
        "psi_error_reason": "FAILED_DOCUMENT_REQUEST (site may be blocking or very slow for Google's test servers)"
    }
    return fallback_result
