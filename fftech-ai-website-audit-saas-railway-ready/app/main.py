import uvicorn
from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging

# Set up logging to see errors in Railway terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.db import Base, engine, get_db
from app.models import User
from app.auth.router import router as auth_router
from app.api.router import router as api_router
from app.services.resend_admin import ensure_resend_ready

app = FastAPI(title='FF Tech AI Website Audit SaaS')

# Global Exception Handler: This will catch errors that cause the "hang"
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"GLOBAL ERROR CAUGHT: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "An internal error occurred during the audit process."},
    )

# Route Registration
app.include_router(auth_router)
app.include_router(api_router)

# Static files and Templates
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

@app.on_event('startup')
def on_startup():
    """Initializes the database and external services on app start."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    try:
        logger.info("Checking Email Service configuration...")
        ensure_resend_ready()
    except Exception as e:
        logger.warning(f"Email service not ready: {e}")
        pass

@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    """Renders the landing page."""
    return templates.TemplateResponse('index.html', {"request": request})

# Added a specific favicon route to stop the 404 logs
@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    from fastapi.responses import FileResponse
    import os
    favicon_path = 'app/static/favicon.ico'
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})

@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Renders the user dashboard if authenticated via session cookie."""
    token = request.cookies.get('session')
    user = None
    if token:
        from app.auth.tokens import decode_token
        payload = decode_token(token)
        if payload:
            email = payload.get('sub')
            user = db.query(User).filter(User.email == email).first()
    return templates.TemplateResponse('dashboard.html', {"request": request, "user": user})

@app.post('/request-login', response_class=RedirectResponse)
async def request_login(email: str = Form(...)):
    """Handles magic link login requests."""
    from app.auth.router import request_link
    try:
        request_link(email)
    except Exception as e:
        logger.error(f"Login Request Failed: {e}")
    return RedirectResponse(url='/', status_code=302)

if __name__ == '__main__':
    # 'app.main:app' ensures uvicorn looks for the 'app' package correctly
    uvicorn.run('app.main:app', host='0.0.0.0', port=8000, reload=True)
