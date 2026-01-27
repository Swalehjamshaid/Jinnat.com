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
    logger.info("🚀 FF Tech International Audit Engine v4.2 initializing...")
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
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
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

    url_param = websocket.query_params.get("url")
    if not url_param:
        await websocket.send_json({"error": "URL parameter is required"})
        await websocket.close(code=1008)
        return

    try:
        normalized_url = normalize_url(url_param)
    except ValueError as e:
        await websocket.send_json({"error": f"Invalid URL: {str(e)}"})
        await websocket.close()
        return

    async def stream_progress(update: Dict[str, Any]):
        """Safely send progress updates to the client"""
        try:
            await websocket.send_json(update)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected during progress streaming")
            raise  # Let outer except handle closure
        except Exception as e:
            logger.warning(f"Failed to send WebSocket update: {e}")

    try:
        logger.info(f"Starting audit for: {normalized_url}")

        # Load PSI API key from environment (Railway vars or .env)
        psi_api_key = os.getenv("PSI_API_KEY")  # Set this in Railway for real LCP/CLS

        runner = WebsiteAuditRunner(
            url=normalized_url,
            max_pages=20,
            psi_api_key=psi_api_key
        )

        # Run the audit and stream progress
        audit_output = await runner.run_audit(progress_callback=stream_progress)

        # Ensure output is a dict
        audit_output = audit_output or {}

        # Log summary for debugging
        bd = audit_output.get("breakdown", {})
        logger.info("Audit completed: %s", {
            "overall_score": audit_output.get("overall_score"),
            "grade": audit_output.get("grade"),
            "seo": bd.get("seo"),
            "lcp_ms": bd.get("performance", {}).get("lcp_ms"),
            "cls": bd.get("performance", {}).get("cls"),
            "internal_links": bd.get("links", {}).get("internal_links_count"),
            "competitor_score": bd.get("competitors", {}).get("top_competitor_score"),
            "audit_time_sec": audit_output.get("audit_time")
        })

        # Build final safe payload for frontend (matches updated runner.py structure)
        final_output = {
            "overall_score": audit_output.get("overall_score", 0),
            "grade": audit_output.get("grade", "D"),
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
            "audit_time": audit_output.get("audit_time", 0.0),
            "finished": True,
            "status": "Audit complete ✔",
            "crawl_progress": 100
        }

        await websocket.send_json(final_output)

    except WebSocketDisconnect:
        logger.info("Client disconnected during audit")
    except Exception as e:
        logger.exception("Audit execution failed")
        await websocket.send_json({
            "error": str(e),
            "status": "Audit failed ❌",
            "finished": True,
            "crawl_progress": 0
        })
    finally:
        try:
            await websocket.close()
        except Exception:
            pass  # Already closed or errored

# ----------------------------
# Health Check Endpoints
# ----------------------------
@app.get("/health")
@app.get("/healthz")
async def health():
    return {
        "status": "healthy",
        "engine": "FF Tech Audit Engine",
        "version": "4.2",
        "timestamp": time.time(),
        "psi_enabled": bool(os.getenv("PSI_API_KEY"))
    }
