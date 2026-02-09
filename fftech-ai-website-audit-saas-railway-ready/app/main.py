# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import logging
from datetime import date
from typing import Any, Dict, Set, Optional

import certifi
import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl, field_validator

# Import audit runner
from app.audit.runner import WebsiteAuditRunner

# ────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s | %(asctime)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("website-audit")

# ────────────────────────────────────────────────
# Paths
# ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
INDEX_HTML = os.path.join(TEMPLATES_DIR, "index.html")

# ────────────────────────────────────────────────
# FastAPI App
# ────────────────────────────────────────────────
app = FastAPI(title="Website Audit Pro", version="1.0.0", docs_url="/docs")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ────────────────────────────────────────────────
# WebSocket Manager
# ────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)

        for connection in dead:
            self.disconnect(connection)

manager = ConnectionManager()

# ────────────────────────────────────────────────
# Models
# ────────────────────────────────────────────────
class AuditRequest(BaseModel):
    url: HttpUrl

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, v: Any) -> str:
        v = str(v).strip()
        if not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v

# ────────────────────────────────────────────────
# Routes
# ────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "time": date.today().isoformat()}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not os.path.isfile(INDEX_HTML):
        logger.error(f"Template not found: {INDEX_HTML}")
        return HTMLResponse("<h3>index.html not found</h3>", status_code=500)
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # discard for now
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.exception("WebSocket error")
        manager.disconnect(websocket)


@app.post("/api/audit/run")
async def run_audit(payload: AuditRequest):
    await manager.broadcast({"type": "progress", "message": "Starting audit...", "percent": 5})

    async def progress_cb(status: str, percent: int, payload: Optional[Dict] = None):
        await manager.broadcast({"type": "progress", "message": status, "percent": percent, "payload": payload})

    runner = WebsiteAuditRunner()
    audit_result = await runner.run(str(payload.url), progress_cb=progress_cb)

    await manager.broadcast({"type": "progress", "message": "Audit completed", "percent": 100})
    return {"ok": True, "data": audit_result}

# ────────────────────────────────────────────────
# Entry point – Fix PORT issue
# ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    # Read PORT from environment variable, default to 8000 if not set
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting server on 0.0.0.0:{port}")

    uvicorn.run(
        "app.main:app",  # module path
        host="0.0.0.0",
        port=port,
        log_level="info",
        # reload=True,   # For development only
    )
