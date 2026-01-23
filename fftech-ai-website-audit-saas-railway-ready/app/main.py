import uvicorn
import os
import logging
from fastapi import FastAPI, Request, Body, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

# Internal Imports
from app.db import get_db, Base, engine
from app.models import AuditLog
from app.audit.grader import WebsiteGrader
from app.services.pdf_generator import PDFService # Matches your requested filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MainApp")

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/open-audit")
async def open_audit(payload: dict = Body(...), db: Session = Depends(get_db)):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    grader = WebsiteGrader()
    try:
        report = await grader.run_full_audit(url)
        new_log = AuditLog(
            url=url,
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
        logger.error(f"Audit processing failed: {e}")
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.get("/api/download-full-audit")
async def download_audit(url: str, db: Session = Depends(get_db)):
    audit = db.query(AuditLog).filter(AuditLog.url == url).order_by(AuditLog.created_at.desc()).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    pdf_service = PDFService()
    pdf_buffer = pdf_service.generate_audit_pdf(audit.raw_data)
    filename = f"Audit_{url.replace('https://', '').replace('/', '_')}.pdf"
    
    return StreamingResponse(
        pdf_buffer, 
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
