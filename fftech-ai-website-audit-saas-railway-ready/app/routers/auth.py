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
    try: yield db
    finally: db.close()

async def send_resend_email(to_email: str, subject: str, html_content: str):
    if not settings.RESEND_API_KEY:
        return

    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": f"{settings.BRAND_NAME} <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }
        )

@router.post('/api/auth/request-link')
async def request_link(payload: dict, db: Session = Depends(get_db)):
    email = payload.get('email')
    if not email:
        raise HTTPException(status_code=400, detail='Email required')
    
    token = serializer.dumps(email)
    
    # Use PUBLIC_URL to match your Railway environment variables
    base_url = getattr(settings, "PUBLIC_URL", "http://localhost:8000")
    link = f"{base_url}/api/auth/verify?token={token}"
    
    html = f"""
    <h3>Sign in to {settings.BRAND_NAME}</h3>
    <p>Click the link below to access your dashboard:</p>
    <a href="{link}" style="padding:10px 20px; background:#2563eb; color:white; text-decoration:none; border-radius:5px;">Sign In Now</a>
    """
    await send_resend_email(email, f"{settings.BRAND_NAME} Login Link", html)
    return {"message": "Verification link sent"}

@router.get('/api/auth/verify')
async def verify(token: str, db: Session = Depends(get_db)):
    try:
        email = serializer.loads(token, max_age=3600)
    except Exception:
        raise HTTPException(status_code=400, detail='Link invalid or expired')
    
    # This query failed before because of the missing column
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.is_verified = True
        db.commit()
    
    return RedirectResponse(url=f"/verify?email={email}")
