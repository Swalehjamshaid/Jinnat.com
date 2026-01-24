import uvicorn
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# ABSOLUTE IMPORTS
from app.db import Base, engine, get_db
from app.models import User
from app.auth.router import router as auth_router
from app.api.router import router as api_router
from app.services.resend_admin import ensure_resend_ready

app = FastAPI(title='FF Tech AI Website Audit SaaS')

# -------------------------
# Include Routers (SAFE)
# -------------------------
app.include_router(auth_router)
app.include_router(api_router)

# -------------------------
# Static & Templates (SAFE)
# -------------------------
app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

# -------------------------
# Startup (SAFE)
# -------------------------
@app.on_event('startup')
def on_startup():
    Base.metadata.create_all(bind=engine)
    try:
        ensure_resend_ready()
    except Exception:
        pass

# -------------------------
# Pages (SAFE)
# -------------------------
@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        'index.html',
        {"request": request}
    )

@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get('session')
    user = None

    if token:
        from app.auth.tokens import decode_token
        payload = decode_token(token)
        if payload:
            email = payload.get('sub')
            user = db.query(User).filter(User.email == email).first()

    return templates.TemplateResponse(
        'dashboard.html',
        {"request": request, "user": user}
    )

# -------------------------
# Local run (SAFE)
# -------------------------
if __name__ == '__main__':
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=8000,
        reload=True
    )
