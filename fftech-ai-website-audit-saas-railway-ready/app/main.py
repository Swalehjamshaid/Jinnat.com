# app/main.py
import json
import logging
import time
import asyncio
from typing import AsyncGenerator
from urllib.parse import urlparse
from fastapi import FastAPI, Request, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

# Import our audit runner
from app.audit.runner import run_audit

# ─────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("audit_engine")

# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FF Tech International Audit Engine starting…")
    yield
    logger.info("FF Tech International Audit Engine stopping…")

app = FastAPI(
    title="FF Tech International Audit Engine",
    version="3.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

# ─────────────────────────────────────────────
# Static Files + Templates
# ─────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ─────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────
def normalize_url(url: str) -> str:
    """Clean & validate URLs before crawling."""
    if not url:
        raise ValueError("URL cannot be empty.")
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL format.")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"

# ─────────────────────────────────────────────
# Home Page
# ─────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ─────────────────────────────────────────────
# WebSocket Audit Endpoint (replaces SSE)
# ─────────────────────────────────────────────
@app.websocket("/ws/audit-progress")
async def websocket_audit(websocket: WebSocket):
    await websocket.accept()

    try:
        url = websocket.query_params.get("url")
        if not url:
            await websocket.send_json({"error": "URL parameter is required"})
            await websocket.close(code=1008)  # Policy violation
            return

        try:
            normalized = normalize_url(url)
        except ValueError as e:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
            return

        # Initial message
        await websocket.send_json({
            "crawl_progress": 0,
            "status": "Connecting...",
            "finished": False
        })
        await asyncio.sleep(0.15)

        await websocket.send_json({
            "crawl_progress": 10,
            "status": "Starting engine…",
            "finished": False
        })
        await asyncio.sleep(0.3)

        await websocket.send_json({
            "crawl_progress": 30,
            "status": "Checking network & SSL…",
            "finished": False
        })
        await asyncio.sleep(0.4)

        # Run the actual audit (blocking call in thread)
        audit_result = await asyncio.to_thread(run_audit, normalized)

        await websocket.send_json({
            "crawl_progress": 80,
            "status": "Building charts & insights…",
            "finished": False
        })
        await asyncio.sleep(0.3)

        # Final result
        final_payload = {
            **audit_result,
            "finished": True,
            "crawl_progress": 100,
            "status": "Audit Complete ✔"
        }
        await websocket.send_json(final_payload)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as e:
        logger.exception("Audit failed via WebSocket for %s", url)
        try:
            await websocket.send_json({
                "finished": True,
                "error": str(e),
                "crawl_progress": 100,
                "status": "Audit failed."
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

# ─────────────────────────────────────────────
# Health Checks
# ─────────────────────────────────────────────
@app.get("/health")
@app.get("/healthz")
async def health():
    return {
        "status": "ok",
        "engine": "FF Tech Audit Engine",
        "version": "3.0",
        "time": time.time(),
    }
