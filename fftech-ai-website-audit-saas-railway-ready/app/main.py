# app/main.py
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

# Internal Imports
from .db import engine, Base, get_db, SessionLocal
from .models import Audit, User
from .audit.runner import run_audit

app = FastAPI(title="FF Tech AI Website Audit SaaS")

# Mount Static and Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def run_migrations():
    """Checks for the missing result_json column and adds it if necessary."""
    with engine.connect() as conn:
        try:
            # Check if column exists
            conn.execute(text("SELECT result_json FROM audits LIMIT 1"))
        except Exception:
            print("MIGRATION: Column 'result_json' not found. Adding it now...")
            conn.execute(text("ALTER TABLE audits ADD COLUMN result_json JSONB"))
            conn.commit()

@app.on_event("startup")
def on_startup():
    # 1. Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    # 2. Fix the specific column error reported in logs
    run_migrations()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/open-audit")
async def open_audit(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        url = body.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL required")

        # Execute the runner (handles SSL and API failures internally)
        result = await run_audit(url)

        # Save to Database
        new_audit = Audit(
            url=url,
            result_json=result
        )
        db.add(new_audit)
        db.commit()
        db.refresh(new_audit)

        return result

    except Exception as e:
        print(f"CRITICAL SERVER ERROR: {e}")
        return JSONResponse({"detail": "Audit failed. Database or Network error."}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
