# app/main.py
import json
import logging
import time
from urllib.parse import urlparse
from typing import Generator

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import run_audit  # ✅ import now works correctly

# ─────────────────────────────────────
# Logging
# ─────────────────────────────────────
logger = logging.getLogger("audit_engine")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

# ─────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────
app = FastAPI(title="FF Tech International Audit Engine", version="2.0")

# Static & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ─────────────────────────────────────
# Utils
# ─────────────────────────────────────
def normalize_url(url: str) -> str:
    if not url:
        raise ValueError("URL is required")

    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL format")

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"

# ─────────────────────────────────────
# Home Page
# ─────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ─────────────────────────────────────
# SSE Generator
# ─────────────────────────────────────
def audit_event_generator(url: str) -> Generator[str, None, None]:
    try:
        yield f"data: {json.dumps({'progress': 5, 'status': 'Starting audit...', 'finished': False})}\n\n"
        time.sleep(0.3)

        yield f"data: {json.dumps({'progress': 20, 'status': 'Crawling website...', 'finished': False})}\n\n"
        time.sleep(0.3)

        result = run_audit(url)

        yield f"data: {json.dumps({'progress': 80, 'status': 'Analyzing results...', 'finished': False})}\n\n"
        time.sleep(0.3)

        result["finished"] = True
        yield f"data: {json.dumps(result)}\n\n"

    except Exception as e:
        logger.exception("Audit error")
        yield f"data: {json.dumps({'finished': True, 'error': str(e)})}\n\n"

# ─────────────────────────────────────
# SSE API
# ─────────────────────────────────────
@app.get("/api/open-audit-progress")
def open_audit_progress(url: str = Query(...)):
    try:
        url = normalize_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StreamingResponse(
        audit_event_generator(url),
        media_type="text/event-stream"
    )

# ─────────────────────────────────────
# Health Check
# ─────────────────────────────────────
@app.get("/healthz")
def health():
    return {"status": "ok"}
