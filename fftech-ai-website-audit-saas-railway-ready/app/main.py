import os
import uvicorn
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Absolute imports
from app.db import Base, engine, get_db
from app.models import User
from app.auth.router import router as auth_router
from app.api.router import router as api_router
from app.services.resend_admin import ensure_resend_ready

app = FastAPI(title='FF Tech AI Website Audit SaaS')

app.include_router(auth_router)
app.include_router(api_router)

app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

@app.on_event('startup')
def on_startup():
    Base.metadata.create_all(bind=engine)
    os.makedirs('storage/reports', exist_ok=True)
    try:
        ensure_resend_ready()
    except Exception:
        pass

@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse('index.html', {"request": request})

@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
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
async def request_login(email: str = Form(...), db: Session = Depends(get_db)):
    from app.auth.router import request_link
    await request_link(email, db)
    return RedirectResponse(url='/?sent=1', status_code=302)

if __name__ == '__main__':
    uvicorn.run('app.main:app', host='0.0.0.0', port=8000, reload=True)
