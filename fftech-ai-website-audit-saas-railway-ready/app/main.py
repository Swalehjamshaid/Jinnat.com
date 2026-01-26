
# app/main.py

import asyncio
import logging
import time
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from app.audit.runner import run_audit


# ---------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("audit_engine")


# ---------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 FF Tech International Audit Engine initializing...")
    yield
    logger.info("🛑 FF Tech International Audit Engine shutting down...")

app = FastAPI(
    title="FF Tech International Audit Engine",
    version="4.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------
# URL Normalizer
# ---------------------------------------------------------
def normalize_url(url: str) -> str:
    """Normalize & validate URL before sending to crawler."""
    if not url:
        raise ValueError("URL cannot be empty.")

    url = url.strip()
    if "://" not in url:
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL format.")

    return parsed.geturl()


# ---------------------------------------------------------
# Home Page
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------
# WebSocket Real‑Time Audit Endpoint
# ---------------------------------------------------------
@app.websocket("/ws/audit-progress")
async def websocket_audit(websocket: WebSocket):

    await websocket.accept()
    url = websocket.query_params.get("url")

    if not url:
        await websocket.send_json({"error": "URL is required"})
        await websocket.close(code=1008)
        return

    try:
        normalized = normalize_url(url)
    except ValueError as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()
        return

    async def stream_progress(update: Dict[str, Any]):
        """Send progress events to WebSocket safely."""
        try:
            await websocket.send_json(update)
        except RuntimeError:
            logger.warning("Client disconnected early; stopping stream.")
            raise WebSocketDisconnect()

    try:
        # Send initial progress
        await stream_progress({"status": "Starting audit…", "crawl_progress": 5})

        # Run the audit asynchronously, streaming progress back
        audit_output = await run_audit(normalized, progress_callback=stream_progress)

        # Send final result
        await stream_progress({
            **audit_output,
            "finished": True,
            "crawl_progress": 100,
            "status": "Audit completed ✔"
        })

    except WebSocketDisconnect:
        logger.info("Client disconnected from audit WebSocket.")
    except Exception as e:
        logger.exception("Audit failed: %s", e)
        await stream_progress({
            "error": str(e),
            "finished": True,
            "status": "Audit failed."
        })

    finally:
        await websocket.close()


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------
@app.get("/health")
@app.get("/healthz")
async def health():
    return {
        "status": "ok",
        "engine": "FF Tech Audit Engine",
        "version": "4.0",
        "time": time.time()
    }
