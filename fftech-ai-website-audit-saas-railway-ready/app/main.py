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
from .db import engine, Base, get_db, SessionLocal
from .models import Audit, User
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
    without crashing the startup transaction.
    """
    with engine.connect() as conn:
        logger.info("Checking database schema integrity...")
        # Querying information_schema is safe and won't abort the transaction
        query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='audits' AND column_name='result_json';
        """)
        
        column_exists = conn.execute(query).fetchone()
        
        if not column_exists:
            logger.warning("MIGRATION: Column 'result_json' missing. Repairing table...")
            try:
                # Use a separate commit for the ALTER command
                conn.execute(text("ALTER TABLE audits ADD COLUMN result_json JSONB;"))
                conn.commit()
                logger.info("MIGRATION: Table 'audits' repaired successfully.")
            except Exception as e:
                logger.error(f"MIGRATION FAILED: {e}")
                conn.rollback()
        else:
            logger.info("SCHEMA CHECK: All columns present.")

@app.on_event("startup")
def startup_event():
    # 1. Create tables if missing
    Base.metadata.create_all(bind=engine)
    # 2. Repair schema if necessary (fixes the result_json error)
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

        # Run the comprehensive runner (handles SSL/PSI failures internally)
        result = await run_audit(url)

        # Persistence: Save the dictionary to our new JSONB column
        new_audit = Audit(
            url=url,
            result_json=result
        )
        db.add(new_audit)
        db.commit()
        db.refresh(new_audit)

        return result

    except Exception as e:
        logger.error(f"API Error: {e}")
        return JSONResponse({"detail": "Internal Server Error during audit processing."}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
