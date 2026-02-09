# -*- coding: utf-8 -*-
"""
app/main.py

Fully integrated FastAPI app for:
- GET /                  -> serves app/templates/index.html
- GET /health            -> health check
- WS  /ws                -> runs audit + streams progress + sends final result (runner_result)
- POST /api/audit/run    -> REST audit fallback (returns runner_result)
- POST /api/audit/pdf    -> generates PDF (returns PDF bytes)

WebSocket message contract:
  stream: { status: str, progress: int, payload: any|null }
  final : { status: "completed", progress: 100, result: runner_result }

runner_result is exactly what runner.py returns:
  { audited_url, overall_score, grade, breakdown, chart_data, dynamic, (optional error) }
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional, Tuple
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl

from app.audit.runner import WebsiteAuditRunner, generate_pdf_from_runner_result

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit_app")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="Website Audit Pro", version="2.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML_PATH = BASE_DIR / "templates" / "index.html"

# ---------------------------------------------------------------------------
# Simple in-memory cache with size limit
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS = int(os.getenv("AUDIT_CACHE_TTL_SECONDS", "900"))
CACHE_MAX_ITEMS = 200
_audit_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    item = _audit_cache.get(key)
    if not item:
        return None
    ts, data = item
    if (time.time() - ts) > CACHE_TTL_SECONDS:
        _audit_cache.pop(key, None)
        return None
    return data


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    if len(_audit_cache) >= CACHE_MAX_ITEMS:
        # remove oldest
        oldest_key = min(_audit_cache.items(), key=lambda x: x[1][0])[0]
        _audit_cache.pop(oldest_key, None)
    _audit_cache[key] = (time.time(), value)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_filename(name: str, default: str = "audit_report") -> str:
    name = (name or "").strip()
    if not name:
        name = default
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("._-") or default
    return name[:90]


def _runner_error_message(result: Dict[str, Any]) -> Optional[str]:
    err = result.get("error")
    return str(err) if err else None


async def _ws_send(ws: WebSocket, message: Dict[str, Any]) -> None:
    try:
        await ws.send_text(json.dumps(message, ensure_ascii=False))
    except Exception:
        # client disconnected
        logger.warning("WebSocket disconnected while sending message.")


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class AuditRunRequest(BaseModel):
    url: HttpUrl = Field(..., description="Website URL (domain or full URL)")


class PdfRequest(BaseModel):
    url: HttpUrl = Field(..., description="Website URL to audit")
    client_name: Optional[str] = ""
    brand_name: Optional[str] = ""
    report_title: Optional[str] = ""
    website_name: Optional[str] = ""
    logo_path: Optional[str] = ""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def index(_: Request) -> HTMLResponse:
    if not INDEX_HTML_PATH.exists():
        return HTMLResponse(
            f"<h3>index.html not found</h3><p>Expected: {INDEX_HTML_PATH}</p>",
            status_code=500,
        )
    return HTMLResponse(INDEX_HTML_PATH.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# WebSocket: /ws
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_audit(ws: WebSocket):
    await ws.accept()
    runner = WebsiteAuditRunner()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": "Invalid JSON"}})
                continue

            url = (msg.get("url") or "").strip()
            if not url:
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": "URL is required"}})
                continue

            cached = _cache_get(url)
            if cached and not _runner_error_message(cached):
                await _ws_send(ws, {"status": "completed", "progress": 100, "result": cached})
                continue

            async def progress_cb(status: str, percent: int, payload: Optional[dict] = None):
                await _ws_send(ws, {"status": status, "progress": int(percent), "payload": payload})

            try:
                result = await runner.run(url, progress_cb=progress_cb)
                _cache_set(url, result)
                err = _runner_error_message(result)
                if err:
                    await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": err, "result": result}})
                    continue
                await _ws_send(ws, {"status": "completed", "progress": 100, "result": result})
            except Exception as e:
                logger.exception("WebSocket audit failed")
                await _ws_send(ws, {"status": "error", "progress": 100, "payload": {"error": str(e)}})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception:
        logger.exception("Unexpected WebSocket error.")

# ---------------------------------------------------------------------------
# REST fallback: /api/audit/run
# ---------------------------------------------------------------------------
@app.post("/api/audit/run")
async def api_audit_run(req: AuditRunRequest) -> JSONResponse:
    url = str(req.url).strip()
    cached = _cache_get(url)
    if cached:
        return JSONResponse(cached)

    runner = WebsiteAuditRunner()
    result = await runner.run(url, progress_cb=None)
    _cache_set(url, result)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# PDF generation: /api/audit/pdf
# ---------------------------------------------------------------------------
@app.post("/api/audit/pdf")
async def api_audit_pdf(req: PdfRequest):
    url = str(req.url).strip()
    runner_result = _cache_get(url)
    if runner_result is None:
        runner = WebsiteAuditRunner()
        try:
            runner_result = await runner.run(url, progress_cb=None)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Audit failed: {e}")
        _cache_set(url, runner_result)

    err = _runner_error_message(runner_result)
    if err:
        raise HTTPException(status_code=400, detail=f"Audit error: {err}")

    report_title = (req.report_title or "").strip() or "Website Audit Report"
    client_name = (req.client_name or "").strip() or "N/A"
    brand_name = (req.brand_name or "").strip() or "FF Tech"
    website_name = (req.website_name or "").strip() or ""
    logo_path = (req.logo_path or "").strip() or None

    fname = _safe_filename(website_name or runner_result.get("audited_url") or "audit_report")

    # Use TemporaryDirectory to auto-clean PDF
    with TemporaryDirectory(prefix="audit_pdf_") as tmp_dir:
        pdf_path = Path(tmp_dir) / f"{fname}.pdf"
        try:
            generate_pdf_from_runner_result(
                runner_result=runner_result,
                output_path=str(pdf_path),
                logo_path=logo_path,
                report_title=report_title,
                client_name=client_name,
                brand_name=brand_name,
                website_name=website_name or None,
                audit_date=None,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

        if not pdf_path.exists():
            raise HTTPException(status_code=500, detail="PDF generation failed (file not created)")

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=pdf_path.name,
            headers={"Content-Disposition": f'attachment; filename="{pdf_path.name}"'},
        )

# ---------------------------------------------------------------------------
# Local run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")
