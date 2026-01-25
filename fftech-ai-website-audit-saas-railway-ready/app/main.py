# app/main.py
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

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/open-audit-progress")
async def open_audit_progress(url: str = Query(...)):
    async def event_stream():
        try:
            yield f"data: {json.dumps({'crawl_progress': 0, 'status': 'Starting audit...'})}\n\n"
            result = await run_audit(url)
            yield f"data: {json.dumps(result)}\n\n"
        except Exception as e:
            logger.exception(f"Audit failed for {url}")
            yield f"data: {json.dumps({'finished': True, 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
