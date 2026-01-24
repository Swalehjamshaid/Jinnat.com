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
from .settings import get_settings  # FIX: Correctly import settings
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
        
        # 1. Check for 'result_json' column
        query_json = text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='audits' AND column_name='result_json';
        """)
        column_exists = conn.execute(query_json).fetchone()
        
        if not column_exists:
            logger.warning("MIGRATION: Column 'result_json' missing. Repairing...")
            try:
                conn.execute(text("ALTER TABLE audits ADD COLUMN result_json JSONB;"))
                conn.commit()
            except Exception as e:
                logger.error(f"MIGRATION FAILED (result_json): {e}")
                conn.rollback()

        # 2. FIX: Check if 'status' column is blocking saves (the NotNullViolation fix)
        try:
            # This makes the status column optional so null values don't crash the app
            conn.execute(text("ALTER TABLE audits ALTER COLUMN status DROP NOT NULL;"))
            conn.commit()
            logger.info("MIGRATION: 'status' column constraint relaxed.")
        except Exception:
            conn.rollback()

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

        # Persistence: Fix the NotNullViolation by explicitly setting status
        new_audit = Audit(
            url=url,
            status="completed",  # FIX: Ensures the DB is happy with this record
            result_json=result
        )
        db.add(new_audit)
        db.commit()
        db.refresh(new_audit)

        return result

    except Exception as e:
        logger.error(f"API Error: {e}")
        # Rollback the DB session on error to prevent transaction hanging
        db.rollback()
        return JSONResponse({"detail": f"Audit failed: {str(e)}"}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
