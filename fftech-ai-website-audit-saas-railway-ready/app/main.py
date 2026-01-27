import time
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
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
    """Handles engine startup and shutdown sequences."""
    logger.info("🚀 FF Tech Audit Engine v4.2 initializing...")
    # Add any startup checks here (e.g., verifying sub-module availability)
    yield
    logger.info("🛑 FF Tech Audit Engine shutting down...")

# ----------------------------
# FastAPI App Instance
# ----------------------------
app = FastAPI(
    title="FF Tech Audit Engine",
    version="4.2",
    docs_url=None,       # Security: Disable default Swagger
    redoc_url=None,      # Security: Disable default Redoc
    lifespan=lifespan
)

# Mount Static Files and Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ----------------------------
# URL Normalizer
# ----------------------------
def normalize_url(url: Optional[str]) -> str:
    """Validates and formats the input URL for consistent processing."""
    if not url:
        raise ValueError("URL is required")
    
    url = url.strip()
    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        
    parsed = urlparse(url)
    # Check for valid structure (domain must exist)
    if not parsed.netloc or "." not in parsed.netloc:
        raise ValueError(f"Invalid domain structure: {url}")
        
    return parsed.geturl()

# ----------------------------
# Routes
# ----------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serves the main audit dashboard UI."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/audit-progress")
async def websocket_audit(websocket: WebSocket):
    """Handles real-time audit streaming via WebSocket."""
    await websocket.accept()
    
    url_param = websocket.query_params.get("url")
    
    try:
        normalized_url = normalize_url(url_param)
        logger.info(f"Starting audit for: {normalized_url}")
    except ValueError as e:
        logger.error(f"URL Validation failed: {e}")
        await websocket.send_json({"error": str(e), "finished": True})
        await websocket.close(code=1008)  # Policy Violation
        return

    async def progress_cb(update: Dict[str, Any]):
        """Callback to stream runner updates to the client."""
        try:
            await websocket.send_json(update)
        except (WebSocketDisconnect, RuntimeError):
            # RuntimeError occurs if we try to send after closure
            pass 

    try:
        # Instantiate Runner with standardized settings
        runner = WebsiteAuditRunner(url=normalized_url, max_pages=50)
        
        # Execute the main audit process
        audit_results = await runner.run_audit(progress_callback=progress_cb)
        
        # Final payload if the runner returns data directly
        if audit_results:
            await websocket.send_json({"results": audit_results, "finished": True})
            
    except WebSocketDisconnect:
        logger.warning(f"Client disconnected early from audit: {normalized_url}")
    except Exception as e:
        logger.exception(f"Audit Engine Crash for {normalized_url}: {e}")
        try:
            await websocket.send_json({"error": "An internal engine error occurred.", "details": str(e), "finished": True})
        except:
            pass
    finally:
        # Ensure socket is closed properly even after failure
        try:
            await websocket.close()
        except:
            pass

# ----------------------------
# Monitoring & Health
# ----------------------------
@app.get("/health", response_class=JSONResponse)
@app.get("/healthz", response_class=JSONResponse)
async def health():
    """System health monitoring endpoint."""
    return {
        "status": "healthy",
        "engine": "FF Tech Audit Engine",
        "version": "4.2",
        "uptime_check": time.time()
    }
