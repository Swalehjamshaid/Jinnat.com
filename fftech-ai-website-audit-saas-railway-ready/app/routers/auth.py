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
        print(f"--- CONSOLE LOG (No API Key) ---\nTo: {to_email}\nSubject: {subject}\nBody: {html_content}")
        return

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": f"{settings.BRAND_NAME} <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }
        )
        if response.status_code != 200:
            print(f"Resend API Error: {response.text}")

@router.post('/api/auth/request-link')
async def request_link(payload: dict, db: Session = Depends(get_db)):
    email = payload.get('email')
    if not email:
        raise HTTPException(status_code=400, detail='Email required')
    
    token = serializer.dumps(email)
    
    # Fix BASE_URL issue
    base = getattr(settings, "PUBLIC_URL", "http://localhost:8000")
    link = f"{base}/api/auth/verify?token={token}"
    
    body = f"""
    <h2>Sign in to {settings.BRAND_NAME}</h2>
    <p>Click the link below to access your website audit dashboard:</p>
    <a href="{link}" style="padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">Sign In Now</a>
    <br><br>
    <p>If you didn't request this, please ignore this email.</p>
    """
    
    await send_resend_email(email, f"{settings.BRAND_NAME} Login Link", body)
    return {"message": "Email sent successfully"}

@router.get('/api/auth/verify')
async def verify(token: str, db: Session = Depends(get_db)):
    try:
        email = serializer.loads(token, max_age=3600)
    except Exception:
        raise HTTPException(status_code=400, detail='Token invalid or expired')
    
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
