# -*- coding: utf-8 -*-
"""
app/main.py

FastAPI entrypoint
- WebSocket-powered website audit
- Streams progress + results from WebsiteAuditRunner
- Serves UI from app/templates/index.html (Jinja2Templates)
- Static mount optional (/static)
- PDF export endpoint

Endpoints:
  GET  /health
  GET  /                 -> serves app/templates/index.html
  GET  /static/*         -> static assets (optional)
  WS   /ws               -> live streaming progress
  POST /api/audit        -> JSON result
  POST /api/audit/pdf    -> PDF download
"""

from __future__ import annotations

import os
import re
import tempfile
import datetime as _dt
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result


# --------------------------------------------------
# App init
# --------------------------------------------------
app = FastAPI(
    title="FF Tech Website Audit Engine",
    docs_url="/docs",
    redoc_url="/redoc",
)


# --------------------------------------------------
# CORS (safe default)
# --------------------------------------------------
cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
allow_origins = ["*"] if cors_origins == "*" else [
    o.strip() for o in cors_origins.split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# UI Hosting (Templates: app/templates/index.html)
# --------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # .../app
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR") or os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.getenv("STATIC_DIR") or os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

INDEX_TEMPLATE = "index.html"
INDEX_PATH = os.path.join(TEMPLATES_DIR, INDEX_TEMPLATE)

# Mount /static if directory exists (optional)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Helpful logs for Railway
print("✅ BASE_DIR      :", BASE_DIR)
print("✅ TEMPLATES_DIR :", TEMPLATES_DIR)
print("✅ INDEX_PATH    :", INDEX_PATH)
print("✅ STATIC_DIR    :", STATIC_DIR)


# --------------------------------------------------
# Health Check (Railway / LB friendly)
# --------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# --------------------------------------------------
# Root UI (serves templates/index.html)
# --------------------------------------------------
@app.get("/")
async def index(request: Request):
    """
    Serves: app/templates/index.html
    """
    if os.path.isfile(INDEX_PATH):
        # Jinja2 requires 'request' in context even if not used in template
        return templates.TemplateResponse(INDEX_TEMPLATE, {"request": request})

    # fallback message if index.html not found
    return HTMLResponse(
        f"""
        <h2>FF Tech Website Audit API</h2>
        <p><strong>UI not found.</strong> Put your dashboard at <code>{INDEX_PATH}</code></p>
        <ul>
          <li>WebSocket: <code>/ws</code></li>
          <li>REST audit: <code>POST /api/audit</code></li>
          <li>PDF export: <code>POST /api/audit/pdf</code></li>
        </ul>
        """,
        status_code=200,
    )


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def _safe_filename(s: str, default: str = "audit") -> str:
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)[:80]
    return s or default


def _today_stamp() -> str:
    return _dt.date.today().isoformat()


def _cleanup_file(path: str) -> None:
    """Best-effort temp file cleanup (PDF)."""
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


# --------------------------------------------------
# WebSocket Audit Endpoint
# --------------------------------------------------
@app.websocket("/ws")
async def websocket_audit(ws: WebSocket):
    """
    Expects first message:
      {"url": "https://example.com"}

    Streams:
      {"progress": 15, "status": "fetching"}
      {"progress": 60, "status": "scoring"}
      {"progress": 100, "status": "completed", "payload": {...result...}}

    Note: runner calls progress_cb("completed", 100, result), so final result usually arrives in payload.
    """
    await ws.accept()
    completed_sent = False

    try:
        payload = await ws.receive_json()
        url = (payload.get("url") or "").strip()

        if not url:
            await ws.send_json({"progress": 100, "status": "error", "error": "URL is required"})
            await ws.close()
            return

        runner = WebsiteAuditRunner()

        async def progress_cb(status: str, percent: int, data: Optional[Dict[str, Any]] = None):
            nonlocal completed_sent
            message: Dict[str, Any] = {"progress": int(percent), "status": status}
            if data is not None:
                message["payload"] = data
            await ws.send_json(message)
            if status == "completed":
                completed_sent = True

        # Run audit (streams progress)
        result = await runner.run(url, progress_cb=progress_cb)

        # Safety fallback: if runner didn't send completed payload, send final result
        if not completed_sent:
            await ws.send_json({"progress": 100, "status": "completed", "result": result})

        await ws.close()

    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await ws.send_json({"progress": 100, "status": "error", "error": str(e)})
            await ws.close()
        except Exception:
            pass


# --------------------------------------------------
# REST: Run Audit (JSON)
# --------------------------------------------------
@app.post("/api/audit")
async def api_audit(payload: Dict[str, Any]):
    """
    JSON API:
      { "url": "https://example.com" }

    Returns runner output with stable keys:
      audited_url, overall_score, grade, breakdown, chart_data, dynamic
    """
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    runner = WebsiteAuditRunner()
    result = await runner.run(url, progress_cb=None)
    return JSONResponse(result)


# --------------------------------------------------
# REST: Generate PDF
# --------------------------------------------------
@app.post("/api/audit/pdf")
async def api_audit_pdf(payload: Dict[str, Any], background: BackgroundTasks):
    """
    Expects:
      { "url": "https://example.com", "client_name": "...", "brand_name": "...", ... }

    Returns: PDF download
    """
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    client_name = (payload.get("client_name") or "").strip() or os.getenv("PDF_CLIENT_NAME", "N/A")
    brand_name = (payload.get("brand_name") or "").strip() or os.getenv("PDF_BRAND_NAME", "FF Tech")
    report_title = (payload.get("report_title") or "").strip() or os.getenv("PDF_REPORT_TITLE", "Website Audit Report")
    website_name = (payload.get("website_name") or "").strip() or None
    logo_path = (payload.get("logo_path") or "").strip() or os.getenv("PDF_LOGO_PATH") or None

    runner = WebsiteAuditRunner()
    result = await runner.run(url, progress_cb=None)

    audited_url = result.get("audited_url") or "website"
    filename = f"{_safe_filename(audited_url)}_{_today_stamp()}.pdf"
    out_path = os.path.join(tempfile.gettempdir(), filename)

    try:
        generate_pdf_from_runner_result(
            runner_result=result,
            output_path=out_path,
            logo_path=logo_path,
            report_title=report_title,
            client_name=client_name,
            brand_name=brand_name,
            audit_date=_today_stamp(),
            website_name=website_name,
        )
    except RuntimeError as e:
        # Most commonly: reportlab not installed
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")

    # cleanup after response is sent
    background.add_task(_cleanup_file, out_path)

    return FileResponse(
        out_path,
        media_type="application/pdf",
        filename=filename,
    )
