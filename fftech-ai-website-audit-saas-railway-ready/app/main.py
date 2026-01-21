import os
import uvicorn
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
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

def fix_database_schema():
    """
    Manually injects missing columns into the database.
    This resolves the 'psycopg2.errors.UndefinedColumn' error on Railway.
    """
    with engine.connect() as conn:
        # We use a PostgreSQL DO block to safely add columns if they don't exist
        conn.execute(text("""
            DO $$ 
            BEGIN 
                BEGIN
                    ALTER TABLE users ADD COLUMN plan VARCHAR(50) DEFAULT 'free';
                EXCEPTION
                    WHEN duplicate_column THEN RAISE NOTICE 'column plan already exists';
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN verification_token VARCHAR(255);
                EXCEPTION
                    WHEN duplicate_column THEN RAISE NOTICE 'column verification_token already exists';
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN token_expiry INTEGER;
                EXCEPTION
                    WHEN duplicate_column THEN RAISE NOTICE 'column token_expiry already exists';
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
                EXCEPTION
                    WHEN duplicate_column THEN RAISE NOTICE 'column created_at already exists';
                END;
                BEGIN
                    ALTER TABLE audits ADD COLUMN overall_score INTEGER DEFAULT 0;
                EXCEPTION
                    WHEN duplicate_column THEN RAISE NOTICE 'column overall_score already exists';
                END;
                BEGIN
                    ALTER TABLE audits ADD COLUMN grade VARCHAR(5) DEFAULT 'F';
                EXCEPTION
                    WHEN duplicate_column THEN RAISE NOTICE 'column grade already exists';
                END;
            END $$;
        """))
        conn.commit()
        print("Database schema migration check complete.")

@app.on_event('startup')
def on_startup():
    # 1. Create tables if they don't exist at all
    Base.metadata.create_all(bind=engine)
    # 2. Force add missing columns to existing tables
    try:
        fix_database_schema()
    except Exception as e:
        print(f"Migration error: {e}")
    # 3. Setup directories
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
