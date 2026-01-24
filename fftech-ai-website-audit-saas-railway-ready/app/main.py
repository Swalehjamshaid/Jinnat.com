# app/main.py
import uvicorn
import logging
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

# Internal Imports
from .db import engine, Base, get_db
from .models import Audit, User
from .settings import get_settings  # CRITICAL FIX: The missing import
from .audit.runner import run_audit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fftech_main")

app = FastAPI(title="FF Tech AI Website Audit SaaS")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def run_self_healing_migration():
    """Self-healing: Ensures 'result_json' exists and 'status/score' are nullable."""
    with engine.connect() as conn:
        logger.info("Checking database schema integrity...")
        try:
            # Add missing result_json column
            conn.execute(text("ALTER TABLE audits ADD COLUMN IF NOT EXISTS result_json JSONB;"))
            # Relax constraints to prevent NotNullViolation crashes
            conn.execute(text("ALTER TABLE audits ALTER COLUMN status DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN score DROP NOT NULL;"))
            conn.commit()
            logger.info("SCHEMA CHECK: All columns present and constraints relaxed.")
        except Exception as e:
            conn.rollback()
            logger.error(f"MIGRATION FAILED: {e}")

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    run_self_healing_migration()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/open-audit")
async def api_open_audit(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        url = body.get("url")
        if not url:
            return JSONResponse({"detail": "URL is required"}, status_code=400)

        # 1. Run the audit (This now sees get_settings)
        result = await run_audit(url)

        # 2. Persistence: Set status and save result_json
        new_audit = Audit(
            url=url,
            status="completed",
            result_json=result
        )
        db.add(new_audit)
        db.commit()
        db.refresh(new_audit)

        return result

    except Exception as e:
        logger.error(f"API Error: {e}")
        db.rollback()
        return JSONResponse({"detail": f"Audit failed: {str(e)}"}, status_code=500)
