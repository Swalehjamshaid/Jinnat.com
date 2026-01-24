# app/main.py
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

# Internal Imports
from .db import engine, Base, get_db
from .models import Audit, User
from .settings import get_settings
from .audit.runner import run_audit

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fftech_main")

app = FastAPI(title="FF Tech AI Website Audit SaaS")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def run_self_healing_migration():
    """
    Checks the PostgreSQL system catalog to safely add missing columns 
    and repair constraints without crashing the startup transaction.
    """
    with engine.connect() as conn:
        logger.info("Checking database schema integrity...")
        
        # 1. Ensure 'result_json' column exists
        try:
            conn.execute(text("ALTER TABLE audits ADD COLUMN IF NOT EXISTS result_json JSONB;"))
            conn.commit()
            logger.info("MIGRATION: 'result_json' column verified.")
        except Exception as e:
            conn.rollback()
            logger.error(f"MIGRATION ERROR (result_json): {e}")

        # 2. Relax 'status' column (NotNullViolation Fix)
        try:
            conn.execute(text("ALTER TABLE audits ALTER COLUMN status DROP NOT NULL;"))
            conn.commit()
            logger.info("MIGRATION: 'status' column constraint relaxed.")
        except Exception:
            conn.rollback()

        # 3. FIX: Relax 'score' column (The NotNullViolation fix from your last logs)
        try:
            conn.execute(text("ALTER TABLE audits ALTER COLUMN score DROP NOT NULL;"))
            conn.commit()
            logger.info("MIGRATION: 'score' column constraint relaxed.")
        except Exception as e:
            conn.rollback()
            logger.error(f"MIGRATION ERROR (score): {e}")

@app.on_event("startup")
def startup_event():
    # Create tables if missing
    Base.metadata.create_all(bind=engine)
    # Perform self-healing schema updates
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

        # Run the comprehensive runner
        result = await run_audit(url)

        # Persistence: We set status and allow score to be null to satisfy DB constraints
        new_audit = Audit(
            url=url,
            status="completed", 
            result_json=result
            # score is omitted because it is now nullable and data is in result_json
        )
        db.add(new_audit)
        db.commit()
        db.refresh(new_audit)

        return result

    except Exception as e:
        logger.error(f"API Error: {e}")
        db.rollback()
        return JSONResponse({"detail": f"Audit failed: {str(e)}"}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
