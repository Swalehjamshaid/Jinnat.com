# app/main.py
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Internal Imports
from .db import engine, Base, get_db
from .models import Audit, User
from .audit.runner import run_audit

# Initialize Database Tables on Startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title='FF Tech AI Audit SaaS')

app.mount('/static', StaticFiles(directory='app/static'), name='static')
templates = Jinja2Templates(directory='app/templates')

# --- PAGE ROUTES ---

@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    """Serves the main landing page."""
    return templates.TemplateResponse('index.html', {"request": request})

@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Pull past audits from the database to show the user."""
    # For now, we fetch all audits. Later, filter by user_id.
    past_audits = db.query(Audit).order_by(Audit.created_at.desc()).all()
    return templates.TemplateResponse('dashboard.html', {
        "request": request,
        "audits": past_audits
    })

# --- API ROUTES ---

@app.post('/api/open-audit')
async def open_audit(request: Request, db: Session = Depends(get_db)):
    """
    The main integration point.
    1. Runs the full audit logic (Crawler -> SEO -> Perf).
    2. Saves the result JSON into the database.
    """
    try:
        body = await request.json()
        url = body.get('url')
        if not url:
            raise HTTPException(status_code=400, detail="URL required")

        # Execute the full audit runner
        result = await run_audit(url)

        # PERSISTENCE: Save result to Database
        new_audit = Audit(
            url=url,
            result_json=result # This captures overall_score, grade, and breakdown
        )
        db.add(new_audit)
        db.commit()
        db.refresh(new_audit)

        return result

    except Exception as e:
        print(f"Server Error: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)

if __name__ == '__main__':
    # Railway environment variables
    uvicorn.run('app.main:app', host='0.0.0.0', port=8080)
