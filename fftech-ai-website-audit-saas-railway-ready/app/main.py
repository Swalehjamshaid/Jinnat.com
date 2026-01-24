# app/main.py
import uvicorn
import logging
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

# Internal Imports
from .db import engine, Base, get_db
from .models import Audit
from .settings import get_settings
from .audit.runner import run_audit

# 1. INITIALIZE APP FIRST (This fixes your NameError)
app = FastAPI(title="FF Tech AI Website Audit SaaS")

# 2. SETUP ASSETS
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# 3. MIGRATION LOGIC
def run_self_healing_migration():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE audits ADD COLUMN IF NOT EXISTS result_json JSONB;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN status DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN score DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN grade DROP NOT NULL;"))
            conn.commit()
        except Exception:
            conn.rollback()

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    run_self_healing_migration()

# 4. ROUTES (Now @app will work)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/open-audit")
async def api_open_audit(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        url = body.get("url")
        result = await run_audit(url)
        new_audit = Audit(url=url, status="completed", result_json=result)
        db.add(new_audit)
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        return JSONResponse({"detail": str(e)}, status_code=500)
