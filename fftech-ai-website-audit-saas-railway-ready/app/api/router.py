from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
import logging

# Internal Imports
from app.db import get_db
from app.audit.grader import WebsiteGrader
from app.models import AuditLog 

router = APIRouter()
logger = logging.getLogger("AuditAPI")

@router.post("/open-audit")
async def open_audit(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    ISO-Standard API endpoint for running website audits.
    """
    target_url = payload.get("url")
    
    if not target_url:
        raise HTTPException(status_code=400, detail="Target URL is required.")

    # Initialize the audit engine
    grader = WebsiteGrader()

    try:
        # Run the full audit
        report = await grader.run_full_audit(target_url)

        # Log results to Database for ISO compliance tracking
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
        logger.error(f"Audit failed for {target_url}: {str(e)}")
        raise HTTPException(status_code=500, detail="Audit Engine Error")
