import os
import uvicorn
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

# Absolute imports
from app.db import Base, engine, get_db
from app.models import User
from app.auth.router import router as auth_router
from app.api.router import router as api_router

app = FastAPI(title='FF Tech AI Website Audit SaaS')

# Include logic routers
app.include_router(auth_router)
app.include_router(api_router)

app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

def fix_database_schema():
    """
    Manually injects missing columns into the PostgreSQL database.
    This resolves the 'psycopg2.errors.UndefinedColumn' error.
    """
    with engine.connect() as conn:
        conn.execute(text("""
            DO $$ 
            BEGIN 
                -- Add 'plan' column
                BEGIN
                    ALTER TABLE users ADD COLUMN plan VARCHAR(50) DEFAULT 'free';
                EXCEPTION WHEN duplicate_column THEN NULL; END;
                
                -- Add 'audit_count' column
                BEGIN
                    ALTER TABLE users ADD COLUMN audit_count INTEGER DEFAULT 0;
                EXCEPTION WHEN duplicate_column THEN NULL; END;

                -- Add 'is_verified' column
                BEGIN
                    ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;
                EXCEPTION WHEN duplicate_column THEN NULL; END;

                -- Add 'verification_token' column
                BEGIN
                    ALTER TABLE users ADD COLUMN verification_token VARCHAR(255);
                EXCEPTION WHEN duplicate_column THEN NULL; END;

                -- Add 'token_expiry' column
                BEGIN
                    ALTER TABLE users ADD COLUMN token_expiry INTEGER;
                EXCEPTION WHEN duplicate_column THEN NULL; END;
            END $$;
        """))
        conn.commit()

@app.on_event('startup')
def on_startup():
    # 1. Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    # 2. Add missing columns to existing tables
    try:
        fix_database_schema()
        print("Database migration check successful.")
    except Exception as e:
        print(f"Migration error: {e}")
    # 3. Setup directories
    os.makedirs('storage/reports', exist_ok=True)

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
            user = db.query(User).filter(User.email == payload.get('sub')).first()
    return templates.TemplateResponse('dashboard.html', {"request": request, "user": user})

@app.post('/request-login', response_class=RedirectResponse)
async def request_login(email: str = Form(...), db: Session = Depends(get_db)):
    from app.auth.router import request_link
    await request_link(email, db)
    return RedirectResponse(url='/?sent=1', status_code=302)

if __name__ == '__main__':
    # Standard Railway port is 8080
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run('app.main:app', host='0.0.0.0', port=port)
