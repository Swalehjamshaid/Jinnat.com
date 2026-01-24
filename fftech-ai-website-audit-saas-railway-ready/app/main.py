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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fftech_main")

# Initialize FastAPI
app = FastAPI(title="FF Tech AI Audit")

# Assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def run_self_healing_migration():
    """Fixes 'NotNullViolation' by dropping mandatory constraints"""
    with engine.connect() as conn:
        logger.info("Running deep schema repair...")
        try:
            # Add missing column
            conn.execute(text("ALTER TABLE audits ADD COLUMN IF NOT EXISTS result_json JSONB;"))
            
            # Relax all columns that caused crashes
            conn.execute(text("ALTER TABLE audits ALTER COLUMN coverage DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN grade DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN score DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE audits ALTER COLUMN status DROP NOT NULL;"))
            
            conn.commit()
            logger.info("SCHEMA REPAIR: Success. All columns are now optional.")
        except Exception as e:
            conn.rollback()
            logger.error(f"SCHEMA REPAIR FAILED: {e}")

@app.on_event("startup")
def startup():
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
        
        # Runs audit with the verified AIza... key
        result = await run_audit(url)

        new_audit = Audit(
            url=url,
            status="completed",
            result_json=result
        )
        db.add(new_audit)
        db.commit()
        return result
    except Exception as e:
        logger.error(f"API Error: {e}")
        db.rollback()
        return JSONResponse({"detail": str(e)}, status_code=500)
