
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from ..db import SessionLocal
from ..models import Schedule, Audit, User
from ..audit.runner import run_audit
from ..audit.report import build_pdf
from ..audit.record import export_xlsx
from .email_reports import send_email_with_attachments

scheduler = BackgroundScheduler()

def job_run_schedules():
    db: Session = SessionLocal()
    try:
        for sc in db.query(Schedule).filter(Schedule.is_active == True).all():
            result = run_audit(sc.url)
            audit = Audit(user_id=sc.user_id, url=sc.url, result_json=result)
            db.add(audit)
            db.commit()
            db.refresh(audit)
            pdf_path = f"/tmp/audit_{audit.id}.pdf"
            build_pdf(result, pdf_path)
            xlsx_path = export_xlsx(result)
            user = db.query(User).filter(User.id==sc.user_id).first()
            if user and user.plan != 'free':
                try:
                    send_email_with_attachments(user.email, f"{result.get('grade','D')} - Website Audit Report", f"<p>Hi,</p><p>Your scheduled audit for <b>{sc.url}</b> is ready.</p>", [pdf_path, xlsx_path])
                except Exception:
                    pass
    finally:
        db.close()

def start_scheduler():
    scheduler.add_job(job_run_schedules, 'interval', hours=24, id='daily_audits', replace_existing=True)
    scheduler.start()
