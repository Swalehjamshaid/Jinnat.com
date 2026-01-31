# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import asyncio
import logging
import datetime as dt
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import httpx
import certifi

# Optional: your WeasyPrint PDF generator (if you already have it)
# from app.audit.pdf_report import generate_audit_pdf

logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(asctime)s | %(name)s | %(message)s")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
INDEX_PATH = os.path.join(TEMPLATES_DIR, "index.html")

logger.info(f"✅ BASE_DIR      : {BASE_DIR}")
logger.info(f"✅ TEMPLATES_DIR : {TEMPLATES_DIR}")
logger.info(f"✅ INDEX_PATH    : {INDEX_PATH}")
logger.info(f"✅ STATIC_DIR    : {STATIC_DIR}")

app = FastAPI(title="Website Audit Pro", version="1.0.0")

# Mount static + templates
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


# -----------------------------
# WebSocket manager (simple)
# -----------------------------
class WSManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = WSManager()


# -----------------------------
# Health + Home
# -----------------------------
@app.get("/health")
def health() -> dict:
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
        # Keep connection alive; if client sends messages, you can handle them here
        while True:
            _ = await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


# -----------------------------
# HTTP fetching with SSL fixes
# -----------------------------
def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def fetch_html_safe(url: str, timeout: float = 25.0) -> Dict[str, Any]:
    """
    Fetch HTML with:
    - verify using certifi CA bundle (best practice in containers)
    - follow redirects
    - if SSL verification fails, retry once with verify=False (audit tool behavior)
    """
    url = normalize_url(url)

    # 1) Strict verify using certifi
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=certifi.where(),
            headers={"User-Agent": "FF-Tech-AuditBot/1.0"},
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return {"ok": True, "url": str(r.url), "status": r.status_code, "html": r.text, "ssl_relaxed": False}
    except httpx.SSLError as e:
        logger.warning(f"SSL verify failed for {url}: {e}. Retrying with relaxed SSL (verify=False).")

        # 2) Retry with relaxed SSL (still encrypted, but not verified)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "FF-Tech-AuditBot/1.0"},
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return {"ok": True, "url": str(r.url), "status": r.status_code, "html": r.text, "ssl_relaxed": True}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": f"HTTP error: {e.response.status_code}", "details": str(e)}
    except Exception as e:
        return {"ok": False, "error": "Fetch failed", "details": str(e)}


# -----------------------------
# Minimal audit logic (replace with your real checks)
# -----------------------------
def run_simple_audit(html: str, url: str) -> Dict[str, Any]:
    """
    Replace this with your real audit checks.
    This is only a safe placeholder.
    """
    title = ""
    lower = html.lower()
    if "<title" in lower:
        # rough parse
        try:
            start = lower.find("<title")
            start = lower.find(">", start) + 1
            end = lower.find("</title>", start)
            title = html[start:end].strip()
        except Exception:
            title = ""

    # Very basic scoring placeholders
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
        "scope": {"what": ["HTML fetch", "Basic title check"], "why": "Health check", "tools": ["httpx", "heuristics"]},
    }


# -----------------------------
# API: Run audit
# -----------------------------
@app.post("/api/audit/run")
async def api_audit_run(payload: Dict[str, Any]):
    """
    Expected input:
    { "url": "example.com" }
    """
    url = payload.get("url") or payload.get("website") or payload.get("website_url")
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    await ws_manager.broadcast({"type": "progress", "message": "Starting audit...", "percent": 5})

    fetch = await fetch_html_safe(url)

    if not fetch.get("ok"):
        await ws_manager.broadcast({"type": "error", "message": fetch.get("error"), "details": fetch.get("details")})
        raise HTTPException(status_code=400, detail=fetch)

    await ws_manager.broadcast(
        {
            "type": "progress",
            "message": f"Fetched HTML (ssl_relaxed={fetch.get('ssl_relaxed')})",
            "percent": 35,
        }
    )

    audit_data = run_simple_audit(fetch["html"], fetch["url"])

    await ws_manager.broadcast({"type": "progress", "message": "Audit completed.", "percent": 100})
    return {"ok": True, "data": audit_data, "ssl_relaxed": fetch.get("ssl_relaxed", False)}


# -----------------------------
# API: PDF export
# -----------------------------
@app.post("/api/audit/pdf")
async def api_audit_pdf(payload: Dict[str, Any]):
    """
    Expected input:
    {
      "audit_data": {...},   # result from /api/audit/run
      "title": "Website Audit Report",
      "logo_path": "app/static/logo.png" (optional)
    }
    """
    audit_data = payload.get("audit_data")
    if not isinstance(audit_data, dict):
        raise HTTPException(status_code=400, detail="audit_data must be provided as a dict")

    report_title = payload.get("title") or "Website Audit Report"
    logo_path = payload.get("logo_path")

    out_dir = os.path.join(BASE_DIR, "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"audit_{int(dt.datetime.utcnow().timestamp())}.pdf")

    # 1) Try WeasyPrint generator if available
    try:
        from app.audit.pdf_report import generate_audit_pdf  # your existing module
        generate_audit_pdf(
            audit_data=audit_data,
            output_path=out_path,
            logo_path=logo_path,
            report_title=report_title,
            base_url=os.getcwd(),
        )
        return FileResponse(out_path, media_type="application/pdf", filename=os.path.basename(out_path))
    except Exception as e:
        logger.warning(f"WeasyPrint PDF failed, falling back to ReportLab. Reason: {e}")

    # 2) Fallback: ReportLab simple PDF
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(out_path, pagesize=A4)
        w, h = A4
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, h - 50, report_title)

        c.setFont("Helvetica", 10)
        c.drawString(40, h - 70, f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Write summary
        audit = audit_data.get("audit", {})
        scores = audit_data.get("scores", {})
        y = h - 110
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Summary")
        y -= 18
        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"Overall Score: {audit.get('overall_score', 'N/A')}")
        y -= 14
        c.drawString(40, y, f"Grade: {audit.get('grade', 'N/A')} | Verdict: {audit.get('verdict', 'N/A')}")
        y -= 22

        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Scores")
        y -= 18
        c.setFont("Helvetica", 10)
        for k, v in scores.items():
            c.drawString(60, y, f"{k}: {v}")
            y -= 14
            if y < 60:
                c.showPage()
                y = h - 60

        c.showPage()
        c.save()
        return FileResponse(out_path, media_type="application/pdf", filename=os.path.basename(out_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed (WeasyPrint + ReportLab): {e}")


# -----------------------------
# Local dev entry (optional)
# -----------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
