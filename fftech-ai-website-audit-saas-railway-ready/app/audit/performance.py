import time, requests, urllib3
urllib3.disable_warnings()

def get_performance_metrics(url: str):
    t0 = time.time()
    try:
        r = requests.get(url, timeout=12, verify=False, headers={"User-Agent": "FFTechAuditor/1.0"})
        ttfb = r.elapsed.total_seconds()
        score = max(0, 100 - (ttfb * 25))
        return {
            "score": round(score, 2),
            "metrics": {
                "77_FCP_ms": int(ttfb * 1000), 
                "91_Server_Response_ms": int(ttfb * 1000), 
                "115_HTTPS": url.startswith('https'),
                "84_Page_Size_KB": round(len(r.content) / 1024, 2)
            },
            "color": "#10B981"
        }
    except:
        return {"score": 0, "metrics": {"91_Error": "Connection Timeout"}, "color": "#EF4444"}
