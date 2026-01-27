import time
import logging
from typing import Any, Dict
from urllib.parse import urlparse
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Use the updated runner
from app.audit.runner import WebsiteAuditRunner

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
# FastAPI Lifespan
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 FF Tech International Audit Engine initializing...")
    yield
    logger.info("🛑 FF Tech International Audit Engine shutting down...")

# ---------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------
app = FastAPI(
    title="FF Tech International Audit Engine",
    version="4.2",
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
    if not url:
        raise ValueError("URL cannot be empty")
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL format")
    return parsed.geturl()

# ---------------------------------------------------------
# Home Page
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ---------------------------------------------------------
# WebSocket Audit Endpoint
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
        normalized_url = normalize_url(url)
    except ValueError as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()
        return

    async def stream_progress(update: Dict[str, Any]):
        try:
            await websocket.send_json(update)
        except RuntimeError:
            logger.warning("WebSocket disconnected early")
            raise WebSocketDisconnect()

    try:
        logger.info(f"Starting audit for {normalized_url}")

        # Initial progress
        await stream_progress({
            "status": "Initializing audit…",
            "crawl_progress": 5,
            "finished": False
        })

        # Run audit
        runner = WebsiteAuditRunner(
            url=normalized_url,
            max_pages=20,  # Adjustable: number of pages to audit
            psi_api_key=None  # Add your Google PSI API key here if available
        )

        audit_output = await runner.run_audit(progress_callback=stream_progress)

        # Final progress
        await stream_progress({
            **audit_output,
            "status": "Audit completed ✔",
            "crawl_progress": 100,
            "finished": True
        })

    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.exception("Audit failed")
        await stream_progress({
            "error": str(e),
            "status": "Audit failed",
            "finished": True
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
        "version": "4.2",
        "time": time.time()
    }
