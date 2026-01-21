import os
import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from ..database import SessionLocal
from ..models import User
from ..config import settings

router = APIRouter()
serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def send_resend_email(to_email: str, subject: str, body: str):
    if not settings.RESEND_API_KEY:
        print(f"SMTP Log (No API Key): To: {to_email} Sub: {subject}")
        return

    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": f"{settings.BRAND_NAME} <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": body
            }
        )

@router.post('/api/auth/request-link')
async def request_link(payload: dict, db: Session = Depends(get_db)):
    email = payload.get('email')
    if not email:
        raise HTTPException(status_code=400, detail='Email required')
    
    token = serializer.dumps(email)
    base = getattr(settings, "PUBLIC_URL", "http://localhost:8000")
    link = f"{base}/api/auth/verify?token={token}"
    
    html = f"""
    <h3>Sign in to {settings.BRAND_NAME}</h3>
    <p>Click below to verify your email and access your dashboard:</p>
    <a href='{link}' style='background:#2563eb; color:white; padding:10px; text-decoration:none;'>Sign In</a>
    """
    await send_resend_email(email, f"{settings.BRAND_NAME} Login Link", html)
    return {"message": "Email sent"}

@router.get('/api/auth/verify')
async def verify(token: str, db: Session = Depends(get_db)):
    try:
        email = serializer.loads(token, max_age=3600)
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid or expired token')
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Create user if they don't exist
        user = User(email=email, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update existing user
        user.is_verified = True
        db.commit()
    
    return RedirectResponse(url=f"/verify?email={email}")
