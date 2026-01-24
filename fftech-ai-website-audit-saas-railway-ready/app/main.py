# app/app/main.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json
import logging

from app.audit.runner import run_audit

logger = logging.getLogger("audit_engine")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FF Tech Audit")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(..., description="Website URL to audit")):
    async def event_stream():
        try:
            yield f"data: {json.dumps({'status': 'Starting audit...'})}\n\n"
            result = await run_audit(url)
            yield f"data: {json.dumps(result)}\n\n"
        except Exception as e:
            logger.exception("Audit failed")
            yield f"data: {json.dumps({'finished': True, 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
