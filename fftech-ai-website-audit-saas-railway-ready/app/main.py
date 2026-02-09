# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import logging
from datetime import date
from typing import Any, Dict, Set

import certifi
import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl, field_validator

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
# App & Templates
# ────────────────────────────────────────────────
app = FastAPI(
    title="Website Audit Pro",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

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
        if not v:
            raise ValueError("URL is required")
        if not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class ProgressMessage(BaseModel):
    type: str = "progress"
    message: str
    percent: int


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
def extract_title(html: str) -> str:
    """Simple but safer title extraction"""
    lower = html.lower()
    start_tag = "<title"
    end_tag = "</title>"

    start_idx = lower.find(start_tag)
    if start_idx == -1:
        return ""

    # Find closing > after <title...>
    tag_close = lower.find(">", start_idx)
    if tag_close == -1:
        return ""

    title_start = tag_close + 1
    title_end = lower.find(end_tag, title_start)
    if title_end == -1:
        return ""

    return html[title_start:title_end].strip()


async def fetch_page(url: str, timeout: float = 25.0) -> dict[str, Any]:
    headers = {"User-Agent": "Website-AuditBot/1.0 (audit; +https://example.com)"}

    # First attempt — strict SSL
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=certifi.where(),
            headers=headers,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {
                "ok": True,
                "url": str(resp.url),
                "status": resp.status_code,
                "html": resp.text,
                "ssl_relaxed": False,
            }
    except httpx.SSLError:
        logger.warning(f"SSL verification failed for {url} → retrying without verification")
    except Exception as e:
        return {"ok": False, "error": "Fetch failed", "details": str(e)}

    # Fallback — no SSL verification
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
            headers=headers,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {
                "ok": True,
                "url": str(resp.url),
                "status": resp.status_code,
                "html": resp.text,
                "ssl_relaxed": True,
            }
    except Exception as e:
        return {"ok": False, "error": "Fetch failed (even without SSL check)", "details": str(e)}


def run_simple_audit(html: str, final_url: str) -> dict:
    title = extract_title(html)

    # Very naive scoring — replace with real logic later
    scores = {
        "seo": 75 if title else 35,
        "performance": 60,
        "security": 70,
        "ux_ui": 65,
        "accessibility": 50,
        "content_quality": 60,
    }

    overall = int(sum(scores.values()) / len(scores))
    grade = "A" if overall >= 85 else "B" if overall >= 70 else "C" if overall >= 55 else "D"

    return {
        "website": {"url": final_url, "title": title or "N/A"},
        "audit": {
            "date": date.today().isoformat(),
            "overall_score": overall,
            "grade": grade,
            "verdict": "Pass" if overall >= 70 else "Needs Improvement",
            "executive_summary": "Basic automated audit completed.",
        },
        "scores": scores,
    }


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
        # Optional: client can send messages → for now we just keep connection
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

    fetch_result = await fetch_page(str(payload.url))

    if not fetch_result["ok"]:
        await manager.broadcast({"type": "error", "message": fetch_result.get("details", "Unknown fetch error")})
        raise HTTPException(400, detail=fetch_result)

    await manager.broadcast({"type": "progress", "message": "Page fetched", "percent": 40})

    audit_result = run_simple_audit(fetch_result["html"], fetch_result["url"])

    await manager.broadcast({"type": "progress", "message": "Audit completed", "percent": 100})

    return {
        "ok": True,
        "data": audit_result,
        "ssl_relaxed": fetch_result["ssl_relaxed"],
    }


# ────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    host = "0.0.0.0"

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "main:app",  # if you rename file → adjust here
        host=host,
        port=port,
        log_level="info",
        # workers=2,   # uncomment for production
        # reload=True, # only in dev
    )
