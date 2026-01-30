# -*- coding: utf-8 -*-
"""
app/main.py

FastAPI entrypoint
- WebSocket-powered website audit
- Streams progress + results from WebsiteAuditRunner
- Compatible with index.html dashboard & PDF export

Works with:
  app/audit/runner.py (stable output keys + optional PDF helpers)

Endpoints:
  GET  /health
  WS   /ws
  POST /api/audit
  POST /api/audit/pdf
"""

from __future__ import annotations

import os
import re
import tempfile
import datetime as _dt
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result


app = FastAPI(title="FF Tech Website Audit Engine")

# -----------------------------
# CORS (safe default)
# -----------------------------
# Tip: set CORS_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
allow_origins = ["*"] if cors_origins == "*" else [o.strip() for o in cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Health Check
# -----------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# -----------------------------
# Helpers
# -----------------------------
def _safe_filename(s: str, default: str = "audit") -> str:
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)[:80]
    return s or default


def _today_stamp() -> str:
    return _dt.date.today().isoformat()


# -----------------------------
# WebSocket Audit Endpoint
# -----------------------------
@app.websocket("/ws")
async def websocket_audit(ws: WebSocket):
    await ws.accept()

    # Prevent duplicate final message:
    # runner.run() already calls progress_cb("completed", 100, result)
    completed_sent = False

    try:
        payload = await ws.receive_json()
        url = (payload.get("url") or "").strip()

        if not url:
            await ws.send_json({
                "progress": 100,
                "status": "error",
                "error": "URL is required",
            })
            await ws.close()
            return

        runner = WebsiteAuditRunner()

        async def progress_cb(status: str, percent: int, data: Optional[Dict[str, Any]] = None):
            nonlocal completed_sent

            msg: Dict[str, Any] = {
                "progress": int(percent),
                "status": status,
            }

            # Runner may send final result in payload at completed
            if data is not None:
                msg["payload"] = data

            await ws.send_json(msg)

            if status == "completed":
                completed_sent = True

        # Run audit (runner streams progress via callback)
        result = await runner.run(url, progress_cb=progress_cb)

        # If runner didn't emit a final completed event for some reason, emit one now.
        if not completed_sent:
            await ws.send_json({
                "progress": 100,
                "status": "completed",
                "result": result,
            })

        await ws.close()

    except WebSocketDisconnect:
        # client closed connection
        return
    except Exception as e:
        try:
            await ws.send_json({
                "progress": 100,
                "status": "error",
                "error": str(e),
            })
            await ws.close()
        except Exception:
            pass


# -----------------------------
# REST: Run Audit (JSON)
# -----------------------------
@app.post("/api/audit")
async def api_audit(payload: Dict[str, Any]):
    """
    JSON API: { "url": "https://example.com" }
    Returns runner output with stable keys:
      audited_url, overall_score, grade, breakdown, chart_data, dynamic
    """
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    runner = WebsiteAuditRunner()
    result = await runner.run(url, progress_cb=None)
    return JSONResponse(result)


# -----------------------------
# REST: Generate PDF
# -----------------------------
@app.post("/api/audit/pdf")
async def api_audit_pdf(payload: Dict[str, Any]):
    """
    PDF Export API:
      {
        "url": "https://example.com",
        "client_name": "ABC Ltd",      (optional)
        "brand_name": "FF Tech",       (optional)
        "report_title": "Website Audit Report", (optional)
        "website_name": "Example",     (optional)
        "logo_path": "app/assets/logo.png" (optional)
      }

    Returns: PDF as downloadable FileResponse.
    """
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    client_name = (payload.get("client_name") or "").strip() or os.getenv("PDF_CLIENT_NAME", "N/A")
    brand_name = (payload.get("brand_name") or "").strip() or os.getenv("PDF_BRAND_NAME", "FF Tech")
    report_title = (payload.get("report_title") or "").strip() or os.getenv("PDF_REPORT_TITLE", "Website Audit Report")
    website_name = (payload.get("website_name") or "").strip() or None
    logo_path = (payload.get("logo_path") or "").strip() or os.getenv("PDF_LOGO_PATH", "") or None

    runner = WebsiteAuditRunner()
    result = await runner.run(url, progress_cb=None)

    # Output path on Railway: /tmp is safe/ephemeral
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
        # Most likely reportlab missing
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")

    return FileResponse(
        out_path,
        media_type="application/pdf",
        filename=filename,
    )


# -----------------------------
# Optional: Simple UI test
# -----------------------------
@app.get("/")
async def index():
    return HTMLResponse("""
    <h2>FF Tech Website Audit API</h2>
    <p>WebSocket endpoint: <code>/ws</code></p>
    <p>REST audit endpoint: <code>POST /api/audit</code></p>
    <p>PDF export endpoint: <code>POST /api/audit/pdf</code></p>
    """)
