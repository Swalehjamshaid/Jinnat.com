# app/app/main.py
import asyncio
import json
import logging
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.audit.runner import run_audit

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FF Tech Python-Only Audit")

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(..., description="Website URL to audit")):
    async def event_stream():
        try:
            yield f"data: {json.dumps({'crawl_progress': 0, 'status': 'Starting Python audit...', 'finished': False})}\n\n"
            result = await run_audit(url)
            result['finished'] = True
            yield f"data: {json.dumps(result)}\n\n"
        except Exception as e:
            logger.exception(f"Audit failed for {url}")
            error_payload = {"finished": True, "error": str(e)}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
