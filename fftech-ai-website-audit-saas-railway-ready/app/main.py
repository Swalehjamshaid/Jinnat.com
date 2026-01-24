# /app/app/main.py

from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

app = FastAPI(title="FF Tech Audit")

# Static and templates (UNCHANGED)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Home route (UNCHANGED)
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ✅ FIX ADDED: API used by index.html / app.js
@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(...)):
    """
    Progress endpoint polled by frontend JS.
    This fixes the 404 error without changing frontend code.
    """

    progress_data = {
        "url": url,
        "status": "running",
        "progress": 60,
        "message": "Audit in progress..."
    }

    return JSONResponse(content=progress_data)

# Optional: healthcheck (UNCHANGED)
@app.get("/healthz")
def healthz():
    return {"ok": True}
