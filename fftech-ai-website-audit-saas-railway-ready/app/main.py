# app/main.py
import os
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

        # ✅ Enable real LCP when PSI key is configured in Railway variables
        psi_api_key = os.getenv("PSI_API_KEY")

        runner = WebsiteAuditRunner(
            url=normalized_url,
            max_pages=20,
            psi_api_key=psi_api_key
        )

        # Run audit with streaming progress
        audit_output = await runner.run_audit(progress_callback=stream_progress)

        if not isinstance(audit_output, dict):
            audit_output = {}

        # Helpful summary in logs for sanity
        bd = audit_output.get("breakdown", {})
        logger.info("Audit output summary: %s", {
            "overall_score": audit_output.get("overall_score"),
            "grade": audit_output.get("grade"),
            "seo": bd.get("seo"),
            "lcp_ms": bd.get("performance", {}).get("lcp_ms"),
            "links": bd.get("links"),
            "competitors": bd.get("competitors"),
        })

        # ✅ Pass through structure; fill safe defaults if any part is missing
        final_output = {
            "overall_score": audit_output.get("overall_score", 0),
            "grade": audit_output.get("grade", "D" if audit_output else "N/A"),
            "breakdown": audit_output.get("breakdown", {
                "seo": 0,
                "links": {
                    "internal_links_count": 0,
                    "external_links_count": 0,
                    "broken_internal_links": 0,
                    "warning_links_count": 0
                },
                "performance": {"lcp_ms": 0, "cls": 0},
                "competitors": {"top_competitor_score": 0}
            }),
            "chart_data": audit_output.get("chart_data", {
                "bar": {"labels": ["SEO", "Links", "Perf", "AI"], "data": [0, 0, 0, 90]},
                "radar": {"labels": ["SEO", "Links", "Perf", "AI"], "data": [0, 0, 0, 90]},
                "doughnut": {"labels": ["Good", "Warning", "Broken"], "data": [0, 0, 0]}
            }),
            "pages_graded": audit_output.get("pages_graded", []),
            "audit_time": audit_output.get("audit_time", 0),
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
