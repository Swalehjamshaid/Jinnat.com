# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple, Union

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketState

from app.audit.runner import WebsiteAuditRunner

# ------------------------------------------------------------
# Logging (Railway-friendly)
# ------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ff-tech-audit")

# ------------------------------------------------------------
# App + Templates
# ------------------------------------------------------------
app = FastAPI(title="FF Tech Audit", version="1.0.0")

# Your templates must be in: app/templates/index.html  OR  templates/index.html
# Adjust if your folder is different. This tries both safely.
_templates_dir = "templates"
if os.path.isdir(os.path.join("app", "templates")):
    _templates_dir = os.path.join("app", "templates")

templates = Jinja2Templates(directory=_templates_dir)

# ------------------------------------------------------------
# Helpers (super flexible parsing + safe send)
# ------------------------------------------------------------
def _extract_url(payload: Any) -> str:
    """
    Accepts many input shapes and extracts URL/domain safely.
    Supports:
      - dict with url/website/domain/link
      - nested dict like {"data":{"url":".."}}
      - plain string "example.com"
    """
    if payload is None:
        return ""

    # plain string
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        # common keys
        for key in ("url", "website", "domain", "link", "target"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        # nested containers
        for key in ("data", "payload", "message", "input"):
            inner = payload.get(key)
            got = _extract_url(inner)
            if got:
                return got

    # unknown format
    return ""


async def _safe_ws_send(ws: WebSocket, message: Dict[str, Any]) -> None:
    """
    Send JSON safely. Never crashes if client disconnected.
    """
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_text(json.dumps(message, ensure_ascii=False))
    except Exception as e:
        logger.warning("WS send failed: %s", e)


async def _send_status(ws: WebSocket, status: str, progress: int, extra: Optional[Dict[str, Any]] = None) -> None:
    msg: Dict[str, Any] = {"status": status, "progress": int(progress)}
    if extra:
        msg.update(extra)
    await _safe_ws_send(ws, msg)


# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Serves the dashboard page.
    Keep this route unchanged to avoid breaking your UI link.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    """
    Simple health check endpoint (optional but useful for Railway).
    """
    return {"ok": True}


# ------------------------------------------------------------
# WebSocket: /ws
# ------------------------------------------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """
    WebSocket endpoint used by the frontend.
    Input:  {url:"..."} or many other shapes
    Output:
      - progress updates: {"status":"...", "progress": N}
      - final result:     {"status":"completed","progress":100,"result":{...}}
      - errors:           {"status":"error","progress":100,"error":"..."}
    """
    await ws.accept()
    await _send_status(ws, "connected", 0)

    runner = WebsiteAuditRunner()
    running_lock = asyncio.Lock()  # prevents overlapping runs on same socket

    while True:
        try:
            raw = await ws.receive_text()

            # Parse JSON if possible, else treat as plain URL string
            payload: Any
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw  # allow plain string

            url = _extract_url(payload)
            if not url:
                await _safe_ws_send(ws, {
                    "status": "error",
                    "progress": 100,
                    "error": "Invalid input. Send JSON like {\"url\":\"example.com\"} or send a plain URL string."
                })
                continue

            # Prevent multiple audits at once per connection
            if running_lock.locked():
                await _send_status(ws, "busy", 0, {"message": "Audit already running. Please wait."})
                continue

            async with running_lock:
                await _send_status(ws, "starting", 5, {"url": url})

                # progress callback from runner -> websocket
                async def progress_cb(status: str, percent: int, data: Optional[dict] = None):
                    # keep message shape stable
                    msg = {"status": status, "progress": int(percent)}
                    if data is not None:
                        # optional attachment; frontend can ignore
                        msg["payload"] = data
                    await _safe_ws_send(ws, msg)

                try:
                    result = await runner.run(url, progress_cb=progress_cb)

                    # If runner reports internal error, still return stable shape
                    if isinstance(result, dict) and result.get("error"):
                        await _safe_ws_send(ws, {
                            "status": "error",
                            "progress": 100,
                            "error": str(result.get("error")),
                            "result": result,  # optional; useful for debugging
                        })
                        continue

                    # Final success
                    await _safe_ws_send(ws, {
                        "status": "completed",
                        "progress": 100,
                        "result": result
                    })

                except Exception as e:
                    logger.exception("Audit run failed")
                    await _safe_ws_send(ws, {
                        "status": "error",
                        "progress": 100,
                        "error": f"Server error: {e}"
                    })

        except WebSocketDisconnect:
            logger.info("Client disconnected")
            break
        except Exception as e:
            logger.exception("WS loop error: %s", e)
            # If something unexpected happens, try to inform client (if still connected)
            await _safe_ws_send(ws, {"status": "error", "progress": 100, "error": f"WS error: {e}"})
            break
