# -*- coding: utf-8 -*-
from __future__ import annotations
import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple, Union

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketState

from app.audit.runner import WebsiteAuditRunner
from app.audit.pdf_report import generate_audit_pdf   # ← added this import

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

_templates_dir = "templates"
if os.path.isdir(os.path.join("app", "templates")):
    _templates_dir = os.path.join("app", "templates")
templates = Jinja2Templates(directory=_templates_dir)

# ------------------------------------------------------------
# Helpers (super flexible parsing + safe send)
# ------------------------------------------------------------
def _extract_url(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("url", "website", "domain", "link", "target"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        for key in ("data", "payload", "message", "input"):
            inner = payload.get(key)
            got = _extract_url(inner)
            if got:
                return got
    return ""

async def _safe_ws_send(ws: WebSocket, message: Dict[str, Any]) -> None:
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
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    return {"ok": True}

# ────────────────────────────────────────────────
# NEW: PDF generation endpoint (called from frontend)
# ────────────────────────────────────────────────
import tempfile

@app.post("/generate-pdf")
async def generate_pdf(payload: Dict[str, Any] = Body(...)):
    """
    Receives the full audit result from frontend → generates PDF → returns file for download
    """
    try:
        # Prepare data structure that pdf_report.py can understand
        audit_data = {
            "website": {
                "url": payload.get("audited_url", "Unknown"),
            },
            "audit": {
                "overall_score": payload.get("overall_score"),
                "grade": payload.get("grade"),
                # You can enrich this later with more context if desired
            },
            "scores": {
                "seo": payload.get("breakdown", {}).get("seo", {}).get("score"),
                "performance": payload.get("breakdown", {}).get("performance", {}).get("score"),
                "links": payload.get("breakdown", {}).get("links", {}).get("score"),
                "security": payload.get("breakdown", {}).get("security", {}).get("score"),
            },
            # Optional: add more detailed sections later
        }

        # Create temporary file (Railway has writable /tmp)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name

        # Generate PDF
        generate_audit_pdf(
            audit_data=audit_data,
            output_path=tmp_path,
            # logo_path="app/assets/logo.png"   # ← uncomment if you have a logo file
        )

        # Prepare clean filename
        domain = payload.get("audited_url", "audit").replace("https://", "").replace("http://", "").replace("/", "_").split("?")[0]
        filename = f"website-audit-report-{domain}.pdf"

        # Return file (FastAPI will handle cleanup after response)
        response = FileResponse(
            path=tmp_path,
            filename=filename,
            media_type="application/pdf"
        )

        # Optional: clean up file after it's sent (best-effort)
        @response.add_middleware
        async def cleanup(request, call_next):
            resp = await call_next(request)
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass
            return resp

        return response

    except Exception as e:
        logger.exception("PDF generation failed")
        return {"status": "error", "message": f"Failed to generate PDF: {str(e)}"}, 500

# ------------------------------------------------------------
# WebSocket: /ws   (unchanged)
# ------------------------------------------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    await _send_status(ws, "connected", 0)
    runner = WebsiteAuditRunner()
    running_lock = asyncio.Lock()

    while True:
        try:
            raw = await ws.receive_text()
            payload: Any
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw

            url = _extract_url(payload)
            if not url:
                await _safe_ws_send(ws, {
                    "status": "error",
                    "progress": 100,
                    "error": "Invalid input. Send JSON like {\"url\":\"example.com\"} or send a plain URL string."
                })
                continue

            if running_lock.locked():
                await _send_status(ws, "busy", 0, {"message": "Audit already running. Please wait."})
                continue

            async with running_lock:
                await _send_status(ws, "starting", 5, {"url": url})

                async def progress_cb(status: str, percent: int, data: Optional[dict] = None):
                    msg = {"status": status, "progress": int(percent)}
                    if data is not None:
                        msg["payload"] = data
                    await _safe_ws_send(ws, msg)

                try:
                    result = await runner.run(url, progress_cb=progress_cb)

                    if isinstance(result, dict) and result.get("error"):
                        await _safe_ws_send(ws, {
                            "status": "error",
                            "progress": 100,
                            "error": str(result.get("error")),
                            "result": result,
                        })
                        continue

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
            await _safe_ws_send(ws, {"status": "error", "progress": 100, "error": f"WS error: {e}"})
            break
