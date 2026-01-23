import uvicorn
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Form, Body, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Internal Imports
from app.db import Base, engine, get_db
from app.models import User, AuditLog
from app.auth.router import router as auth_router
from app.api.router import router as api_router
from app.settings import get_settings
from app.audit.grader import WebsiteGrader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("--- FASTAPI STARTUP: Initializing Services ---")
    Base.metadata.create_all(bind=engine)
    yield
    logger.info("--- FASTAPI SHUTDOWN ---")

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.include_router(auth_router)
app.include_router(api_router)

app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse('index.html', {"request": request, "settings": settings})

@app.post('/api/open-audit')
async def open_audit(payload: dict = Body(...), db: Session = Depends(get_db)):
    target_url = payload.get("url")
    if not target_url:
        return JSONResponse(status_code=400, content={"message": "URL required"})
    
    # Initialize Grader - It will pull GOOGLE_API_KEY from os.environ
    grader = WebsiteGrader()
    
    try:
        report = await grader.run_full_audit(target_url)
        
        # Save to Database
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
        logger.error(f"Audit failed: {e}")
        return JSONResponse(status_code=500, content={"message": "Audit failed. Check API Key quotas."})

@app.get('/api/download-full-audit')
async def download_audit(url: str, db: Session = Depends(get_db)):
    """
    FIXED: This resolves the 404 error in your logs.
    For now, it returns the JSON data. (We can integrate PDF generation next).
    """
    audit = db.query(AuditLog).filter(AuditLog.url == url).order_by(AuditLog.created_at.desc()).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found. Please run a scan first.")
    
    return JSONResponse(content=audit.raw_data)

if __name__ == '__main__':
    uvicorn.run('app.main:app', host='0.0.0.0', port=8080, reload=True)
