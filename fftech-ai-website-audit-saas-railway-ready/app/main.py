import uvicorn
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Internal Imports
from app.db import Base, engine, get_db
from app.models import User, AuditLog
from app.auth.router import router as auth_router
from app.api.router import router as api_router
from app.services.resend_admin import ensure_resend_ready
from app.settings import get_settings
from app.audit.grader import WebsiteGrader  # Ensure this import is correct

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown logic."""
    logger.info("--- FASTAPI STARTUP: Initializing Services ---")
    Base.metadata.create_all(bind=engine)
    try:
        logger.info("Checking Email Service configuration...")
        ensure_resend_ready()
    except Exception as e:
        logger.warning(f"Email service not ready: {e}")
    yield
    logger.info("--- FASTAPI SHUTDOWN ---")

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"GLOBAL ERROR: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error"},
    )

app.include_router(auth_router)
app.include_router(api_router)

app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse('index.html', {"request": request, "settings": settings})

@app.post('/api/open-audit')
async def open_audit(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    FIXED: Properly initializes WebsiteGrader and calls run_full_audit.
    """
    target_url = payload.get("url")
    if not target_url:
        return JSONResponse(status_code=400, content={"message": "URL required"})
    
    try:
        # 1. Initialize the Class
        grader = WebsiteGrader()
        
        # 2. Call the correct async method
        report = await grader.run_full_audit(target_url)
        
        # 3. Save to AuditLog (ISO Standard Tracking)
        new_log = AuditLog(
            url=target_url,
            status=report["connectivity"]["status"],
            error_code=report["connectivity"]["error_code"],
            performance_score=report["score"],
            execution_time=report["metadata"]["duration"],
            raw_data=report
        )
        db.add(new_log)
        db.commit()
        
        return report
    except Exception as e:
        logger.error(f"Audit processing failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse('app/static/favicon.ico')

if __name__ == '__main__':
    uvicorn.run('app.main:app', host='0.0.0.0', port=8080, reload=True)
