# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import datetime as dt
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Body, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketState

from app.audit.runner import WebsiteAuditRunner
from app.audit.pdf_service import generate_pdf_from_runner_result  # ✅ adapter (best practice)

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


async def _send_status(
    ws: WebSocket,
    status: str,
    progress: int,
    extra: Optional[Dict[str, Any]] = None
) -> None:
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

# ------------------------------------------------------------
# PDF Generation Endpoint (best-practice integration, backward compatible)
# ------------------------------------------------------------
@app.post("/generate-pdf")
async def generate_pdf(
    background_tasks: BackgroundTasks,              # ✅ non-default first
    payload: Dict[str, Any] = Body(...),            # ✅ default after
):
    """
    Backward compatible endpoint:

    Accepts either:
      A) runner result directly (existing UI):
         { audited_url, overall_score, grade, breakdown, chart_data, dynamic }

      OR

      B) extended payload for better cover page:
         {
           "client_name": "ABC",
           "brand_name": "FF Tech",
           "audit_date": "2026-01-30",
           "website_name": "My Site",
           "result": { ...runner result... }
         }

    Generates PDF and returns it.
    """
    tmp_path = None
    try:
        # ----------------------------------------
        # 1) Detect payload shape
        # ----------------------------------------
        if isinstance(payload.get("result"), dict):
            runner_result = payload.get("result") or {}
            client_name = str(payload.get("client_name") or "N/A")
            brand_name = str(payload.get("brand_name") or "FF Tech")
            audit_date = str(payload.get("audit_date") or dt.date.today().isoformat())
            website_name = payload.get("website_name")
        else:
            # Old format: payload IS runner_result
            runner_result = payload
            client_name = "N/A"
            brand_name = "FF Tech"
            audit_date = dt.date.today().isoformat()
            website_name = None

        # ----------------------------------------
        # 2) Create temp file
        # ----------------------------------------
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name

        logger.info("Generating PDF to: %s", tmp_path)

        # ----------------------------------------
        # 3) Generate PDF via adapter (best practice)
        # ----------------------------------------
        generate_pdf_from_runner_result(
            runner_result=runner_result,
            output_path=tmp_path,
            logo_path=None,             # add if you have a logo file path
            client_name=client_name,
            brand_name=brand_name,
            audit_date=audit_date,
            website_name=website_name,
        )

        # ----------------------------------------
        # 4) Filename
        # ----------------------------------------
        audited_url = str(runner_result.get("audited_url", "report"))
        domain = (
            audited_url
            .replace("https://", "")
            .replace("http://", "")
            .replace("/", "_")
            .replace("www.", "")
            .split("?")[0]
            .strip()
        )
        filename = f"website-audit-report-{domain}.pdf"

        # ----------------------------------------
        # 5) Cleanup after response
        # ----------------------------------------
        def cleanup():
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    logger.info("Cleaned up: %s", tmp_path)
            except Exception as e:
                logger.warning("Cleanup failed for %s: %s", tmp_path, e)

        background_tasks.add_task(cleanup)

        return FileResponse(
            path=tmp_path,
            filename=filename,
            media_type="application/pdf"
        )

    except Exception as e:
        logger.exception("PDF generation failed")

        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to generate PDF: {str(e)}"}
        )

# ------------------------------------------------------------
# WebSocket: /ws (unchanged)
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
