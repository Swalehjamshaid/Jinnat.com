# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import asyncio
import logging
import datetime as dt
from typing import Any, Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import httpx
import certifi

# -------------------------------------------------
# Logging
# -------------------------------------------------
logger = logging.getLogger("app.main")
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(asctime)s | %(name)s | %(message)s",
)

# -------------------------------------------------
# Paths
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
INDEX_PATH = os.path.join(TEMPLATES_DIR, "index.html")

logger.info(f"BASE_DIR      : {BASE_DIR}")
logger.info(f"TEMPLATES_DIR : {TEMPLATES_DIR}")
logger.info(f"STATIC_DIR    : {STATIC_DIR}")
logger.info(f"INDEX_PATH    : {INDEX_PATH}")

# -------------------------------------------------
# App
# -------------------------------------------------
app = FastAPI(title="Website Audit Pro", version="1.0.0")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# -------------------------------------------------
# WebSocket Manager
# -------------------------------------------------
class WSManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = WSManager()

# -------------------------------------------------
# Health & Home
# -------------------------------------------------
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "time": dt.datetime.utcnow().isoformat() + "Z"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if not os.path.exists(INDEX_PATH):
        return HTMLResponse("<h3>index.html not found in templates</h3>", status_code=500)
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)

# -------------------------------------------------
# URL & Fetch Helpers
# -------------------------------------------------
def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def fetch_html_safe(url: str, timeout: float = 25.0) -> Dict[str, Any]:
    url = normalize_url(url)

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=certifi.where(),
            headers={"User-Agent": "FF-Tech-AuditBot/1.0"},
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return {
                "ok": True,
                "url": str(r.url),
                "status": r.status_code,
                "html": r.text,
                "ssl_relaxed": False,
            }
    except httpx.SSLError:
        logger.warning(f"SSL verify failed for {url}, retrying relaxed.")
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "FF-Tech-AuditBot/1.0"},
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return {
                "ok": True,
                "url": str(r.url),
                "status": r.status_code,
                "html": r.text,
                "ssl_relaxed": True,
            }
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": f"HTTP error: {e.response.status_code}", "details": str(e)}
    except Exception as e:
        return {"ok": False, "error": "Fetch failed", "details": str(e)}

# -------------------------------------------------
# Audit Logic (unchanged behavior)
# -------------------------------------------------
def run_simple_audit(html: str, url: str) -> Dict[str, Any]:
    title = ""
    lower = html.lower()
    if "<title" in lower:
        try:
            start = lower.find("<title")
            start = lower.find(">", start) + 1
            end = lower.find("</title>", start)
            title = html[start:end].strip()
        except Exception:
            title = ""

    scores = {
        "seo": 70 if title else 40,
        "performance": 60,
        "security": 75,
        "ux_ui": 65,
        "accessibility": 55,
        "content_quality": 60,
    }
    overall = int(sum(scores.values()) / len(scores))

    return {
        "website": {"url": url, "name": title or "N/A"},
        "audit": {
            "date": dt.date.today().isoformat(),
            "overall_score": overall,
            "grade": "A" if overall >= 85 else ("B" if overall >= 70 else ("C" if overall >= 55 else "D")),
            "verdict": "Pass" if overall >= 70 else "Needs Improvement",
            "executive_summary": "Automated audit completed successfully.",
        },
        "scores": scores,
        "seo": {"on_page_issues": [], "technical_issues": []},
        "performance": {"page_size_issues": []},
        "scope": {
            "what": ["HTML fetch", "Basic title check"],
            "why": "Health check",
            "tools": ["httpx", "heuristics"],
        },
    }

# -------------------------------------------------
# API Endpoints (UNCHANGED)
# -------------------------------------------------
@app.post("/api/audit/run")
async def api_audit_run(payload: Dict[str, Any]):
    url = payload.get("url") or payload.get("website") or payload.get("website_url")
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    await ws_manager.broadcast({"type": "progress", "message": "Starting audit...", "percent": 5})

    fetch = await fetch_html_safe(url)
    if not fetch.get("ok"):
        await ws_manager.broadcast({"type": "error", "message": fetch.get("error")})
        raise HTTPException(status_code=400, detail=fetch)

    await ws_manager.broadcast(
        {"type": "progress", "message": "Fetched HTML", "percent": 35}
    )

    audit_data = run_simple_audit(fetch["html"], fetch["url"])

    await ws_manager.broadcast({"type": "progress", "message": "Audit completed.", "percent": 100})
    return {"ok": True, "data": audit_data, "ssl_relaxed": fetch.get("ssl_relaxed", False)}

# -------------------------------------------------
# Local / Cloud Entry Point (FIXED)
# -------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
