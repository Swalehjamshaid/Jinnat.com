# app/main.py
import time
import logging
from typing import Any, Dict
from urllib.parse import urlparse
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import WebsiteAuditRunner

# ----------------------------
# Logging Setup
# ----------------------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
logger = logging.getLogger("audit_engine")

# ----------------------------
# FastAPI Lifespan
# ----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 FF Tech Audit Engine initializing...")
    yield
    logger.info("🛑 FF Tech Audit Engine shutting down...")

# ----------------------------
# FastAPI App
# ----------------------------
app = FastAPI(title="FF Tech Audit Engine", version="4.2", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ----------------------------
# URL Normalizer
# ----------------------------
def normalize_url(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL")
    return parsed.geturl()

# ----------------------------
# Home Page
# ----------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ----------------------------
# WebSocket Audit Endpoint
# ----------------------------
@app.websocket("/ws/audit-progress")
async def websocket_audit(websocket: WebSocket):
    await websocket.accept()
    url = websocket.query_params.get("url")
    if not url:
        await websocket.send_json({"error": "URL required"})
        await websocket.close(code=1008)
        return

    try:
        normalized_url = normalize_url(url)
    except ValueError as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()
        return

    async def progress_cb(update: Dict[str, Any]):
        try:
            await websocket.send_json(update)
        except WebSocketDisconnect:
            logger.warning("Client disconnected")

    try:
        runner = WebsiteAuditRunner(url=normalized_url, max_pages=50)
        await runner.run_audit(progress_callback=progress_cb)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        await websocket.send_json({"error": str(e), "finished": True})
    finally:
        await websocket.close()

# ----------------------------
# Health Check
# ----------------------------
@app.get("/health")
@app.get("/healthz")
async def health():
    return {"status": "ok", "engine": "FF Tech Audit Engine", "version": "4.2", "time": time.time()}
