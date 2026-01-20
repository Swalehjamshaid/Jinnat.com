
# app/main.py
import os
from typing import Optional, Dict, Any

from fastapi import FastAPI, Depends, Request, HTTPException, Response, Body
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
from sqlalchemy import text, select, func

import jwt

from .db import engine, get_db, try_connect_with_retries_and_create_tables
from .models import User, Audit
from .schemas import AuditCreate, AuditResponse
from .audit.compute import audit_site_sync
from .report.report import build_pdf
from .report.record import export_xlsx, export_pptx
from .auth import router as auth_router
from .config import settings

app = FastAPI(title="FF Tech – AI Website Audit")

# Static and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Auth routes
app.include_router(auth_router)

JWT_ALG = settings.JWT_ALG


# -----------------------------
# Dependencies & startup
# -----------------------------
def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """
    Read the session cookie and return the current User or None.
    This function is synchronous and should not be awaited.
    """
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALG])
        uid = int(data["sub"])
        return db.get(User, uid)
    except Exception:
        return None


@app.on_event("startup")
def on_startup():
    """
    On startup:
      - connect to DB with retries (handles Railway cold starts)
      - auto-create tables once connection is up
    """
    print("[SYSTEM] Starting up…")
    try_connect_with_retries_and_create_tables()


# -----------------------------
# Health
# -----------------------------
@app.get("/health/db")
def db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


# -----------------------------
# Pages
# -----------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: Optional[User] = Depends(get_current_user)):
    if not user:
        # use redirect instead of inline meta refresh
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})


# -----------------------------
# API – Audit
# -----------------------------
@app.post("/api/audit", response_model=AuditResponse)
async def run_audit(
    payload: AuditCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    user_id = user.id if user else None

    # Enforce free quota for non-paid users
    if user:
        # SQLAlchemy 2.0 style count
        total = db.scalar(
            select(func.count()).select_from(Audit).where(Audit.user_id == user.id)
        ) or 0
        if not user.is_paid and total >= 10:
            raise HTTPException(402, detail="Free quota exceeded. Upgrade to continue.")

    # Run audit (deterministic, offline-friendly in current setup)
    result = audit_site_sync(str(payload.url))
    overall = result["overall"]

    # Persist only for signed-in users
    audit = Audit(
        user_id=user_id,
        url=str(payload.url),
        status="completed",
        score=overall["score"],
        grade=overall["grade"],
        coverage=overall["coverage"],
        metrics=result["metrics"],
        summary=result["summary"],
    )
    if user:
        db.add(audit)
        db.commit()
        db.refresh(audit)
        audit_id = audit.id
    else:
        audit_id = 0

    return AuditResponse(
        id=audit_id,
        url=str(payload.url),
        score=overall["score"],
        grade=overall["grade"],
        coverage=overall["coverage"],
        summary=result["summary"],
        metrics=result["metrics"],
    )


@app.get("/api/audit/list")
async def list_audits(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, detail="Not signed in")

    stmt = (
        select(Audit)
        .where(Audit.user_id == user.id)
        .order_by(Audit.id.desc())
        .limit(50)
    )
    items = db.execute(stmt).scalars().all()

    return [
        {
            "id": a.id,
            "url": a.url,
            "score": a.score,
            "grade": a.grade,
            "coverage": a.coverage,
            "created_at": a.created_at.isoformat(),
        }
        for a in items
    ]


# -----------------------------
# API – Reports (stored)
# -----------------------------
@app.get("/api/report/pdf/{audit_id}")
async def report_pdf(audit_id: int, db: Session = Depends(get_db)):
    a = db.get(Audit, audit_id)
    if not a:
        raise HTTPException(404, detail="Audit not found")

    pdf = build_pdf({
        "overall": {"score": a.score, "grade": a.grade, "coverage": a.coverage},
        "metrics": a.metrics,
    })
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=fftech_audit_{a.id}.pdf"},
    )


@app.get("/api/report/xlsx/{audit_id}")
async def report_xlsx(audit_id: int, db: Session = Depends(get_db)):
    a = db.get(Audit, audit_id)
    if not a:
        raise HTTPException(404, detail="Audit not found")

    x = export_xlsx({
        "metrics": a.metrics,
        "overall": {"score": a.score, "grade": a.grade, "coverage": a.coverage},
    })
    return Response(
        content=x,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=fftech_audit_{a.id}.xlsx"},
    )


@app.get("/api/report/pptx/{audit_id}")
async def report_pptx(audit_id: int, db: Session = Depends(get_db)):
    a = db.get(Audit, audit_id)
    if not a:
        raise HTTPException(404, detail="Audit not found")

    p = export_pptx({
        "metrics": a.metrics,
        "overall": {"score": a.score, "grade": a.grade, "coverage": a.coverage},
    })
    return Response(
        content=p,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f"attachment; filename=fftech_audit_{a.id}.pptx"},
    )


# -----------------------------
# API – Reports (open on-the-fly)
# -----------------------------
@app.post("/api/report/pdf-open")
async def report_pdf_open(payload: Dict[str, Any] = Body(...)):
    overall = payload.get("overall") or {
        "score": payload.get("score", 0),
        "grade": payload.get("grade", "D"),
        "coverage": payload.get("coverage", 0),
    }
    metrics = payload.get("metrics") or {}
    pdf = build_pdf({"overall": overall, "metrics": metrics})
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=fftech_audit.pdf"},
    )
