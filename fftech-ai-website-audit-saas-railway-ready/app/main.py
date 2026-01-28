# app/main.py
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.audit.runner import WebsiteAuditRunner  # Assuming your audit runner is here

app = FastAPI(title="FF Tech Audit Engine v6")

# -------------------------
# Serve static frontend
# -------------------------
# Make sure your index.html is in app/static/
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root route serves the frontend HTML
    """
    return FileResponse("app/static/index.html")


# -------------------------
# API Endpoints
# -------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Backend running successfully"}

@app.get("/api/audit-start")
async def audit_start(url: str):
    """
    Start audit process (polling-compatible)
    Returns a job_id (simple placeholder for now)
    """
    # For simplicity, generate a dummy job_id
    job_id = url.replace("://","_").replace("/","_")
    # In real implementation, trigger audit runner async here
    return {"job_id": job_id, "status": "audit started"}

@app.get("/api/audit-poll")
async def audit_poll(job_id: str):
    """
    Poll audit result
    """
    # Placeholder response
    return {
        "finished": True,
        "overall_score": 85,
        "grade": "B+",
        "chart_data": {},
        "breakdown": {
            "seo": {"score": 80},
            "performance": {"score": 90, "lcp_ms": 1200},
            "links": {"internal_links_count": 45, "external_links_count": 12, "broken_internal_links": 0},
            "competitors": {"names": ["comp1","comp2"], "items":[{"name":"comp1","score":87},{"name":"comp2","score":82}]}
        }
    }

# -------------------------
# WebSocket / SSE endpoints
# Optional: Add your real WS / SSE here if needed
# -------------------------


# -------------------------
# Start server
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
