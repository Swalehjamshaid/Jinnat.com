import time
import logging
from typing import Any, Dict
from urllib.parse import urlparse
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import WebsiteAuditRunner

# ----------------------------
# Logging Setup
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("audit_engine")

# ----------------------------
# FastAPI Lifespan
# ----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 FF Tech International Audit Engine initializing...")
    yield
    logger.info("🛑 FF Tech International Audit Engine shutting down...")

# ----------------------------
# FastAPI App
# ----------------------------
app = FastAPI(
    title="FF Tech International Audit Engine",
    version="4.2",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ----------------------------
# URL Normalizer
# ----------------------------
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
        """Send updates to frontend safely"""
        try:
            await websocket.send_json(update)
        except Exception:
            logger.warning("WebSocket disconnected during progress update")
            raise WebSocketDisconnect()

    try:
        logger.info(f"Starting audit for {normalized_url}")

        runner = WebsiteAuditRunner(
            url=normalized_url,
            max_pages=20,
            psi_api_key=None
        )

        # Run audit with streaming progress
        audit_output = await runner.run_audit(progress_callback=stream_progress)

        # Structure the data for the frontend
        final_output = {
            "overall_score": audit_output.get("overall_score", 0),
            "grade": audit_output.get("grade", "N/A"),
            "breakdown": {
                "seo": audit_output.get("seo_score", 0),
                "performance": {
                    "lcp_ms": audit_output.get("lcp_ms", 0),
                    "cls": audit_output.get("cls", 0),
                },
                "competitors": {
                    "top_competitor_score": audit_output.get("top_competitor_score", 0)
                },
                "links": {
                    "internal_links_count": audit_output.get("internal_links", 0),
                    "external_links_count": audit_output.get("external_links", 0),
                    "broken_internal_links": audit_output.get("broken_links", 0)
                }
            },
            "chart_data": audit_output.get("chart_data", {
                "bar": {
                    "labels": ["SEO", "Performance", "Competitors", "AI Confidence"],
                    "data": [0, 0, 0, 0]
                },
                "radar": {
                    "labels": ["SEO", "Performance", "Competitors", "AI Confidence"],
                    "data": [0, 0, 0, 0]
                }
            }),
            "finished": True,
            "status": "Audit complete ✔",
            "crawl_progress": 100
        }

        await websocket.send_json(final_output)

    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.exception("Audit failed")
        await websocket.send_json({
            "error": str(e),
            "status": "Audit failed",
            "finished": True
        })
    finally:
        await websocket.close()

# ----------------------------
# Health Check
# ----------------------------
@app.get("/health")
@app.get("/healthz")
async def health():
    return {
        "status": "ok",
        "engine": "FF Tech Audit Engine",
        "version": "4.2",
        "time": time.time()
    }
