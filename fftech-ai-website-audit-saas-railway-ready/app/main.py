import uvicorn
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Internal imports
from app.db import Base, engine, get_db
from app.models import User
from app.auth.router import router as auth_router
from app.api.router import router as api_router
from app.services.resend_admin import ensure_resend_ready
from app.settings import get_settings

# Import WebsiteGrader correctly
from app.audit import grader  # import the module
WebsiteGrader = grader  # use module directly if class is not defined

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown logic"""
    logger.info("--- FASTAPI STARTUP: Initializing Services ---")
    # Create database tables
    Base.metadata.create_all(bind=engine)
    # Check email service
    try:
        logger.info("Checking Email Service configuration...")
        ensure_resend_ready()
    except Exception as e:
        logger.warning(f"Email service not ready: {e}")
    yield
    logger.info("--- FASTAPI SHUTDOWN: Cleaning up ---")

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"GLOBAL ERROR CAUGHT: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": f"Server Audit Error: {str(exc)}"},
    )

# Routers
app.include_router(auth_router)
app.include_router(api_router)

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "settings": settings})

@app.post("/api/open-audit")
async def open_audit(payload: dict = Body(...)):
    target_url = payload.get("url")
    if not target_url:
        return JSONResponse(status_code=400, content={"message": "URL is required"})
    try:
        # Use WebsiteGrader module directly
        report = grader.run_audit(target_url)  # Assuming run_audit(url) exists in grader.py
        return report
    except Exception as e:
        logger.error(f"Audit processing failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"message": "Failed to analyze site."})

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = "app/static/favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    user = None
    if token:
        from app.auth.tokens import decode_token
        payload = decode_token(token)
        if payload:
            email = payload.get("sub")
            user = db.query(User).filter(User.email == email).first()
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "settings": settings})

@app.post("/request-login", response_class=RedirectResponse)
async def request_login(email: str = Form(...)):
    from app.auth.router import request_link
    try:
        request_link(email)
    except Exception as e:
        logger.error(f"Login Request Failed: {e}", exc_info=True)
    return RedirectResponse(url="/", status_code=302)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
