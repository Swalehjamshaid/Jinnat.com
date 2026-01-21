import os
import httpx  # Added for Resend API calls
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

async def send_resend_email(to_email: str, subject: str, html_content: str):
    """
    Uses the Resend API Key to send actual emails.
    """
    if not settings.RESEND_API_KEY:
        print('=== EMAIL (Console Only - Key Missing) ===')
        print(f'TO: {to_email}\nSUBJECT: {subject}\n{html_content}')
        return

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{settings.BRAND_NAME} <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            },
        )
        if response.status_code != 200:
            print(f"Resend Error: {response.text}")

@router.post('/api/auth/request-link')
async def request_link(payload: dict, db: Session = Depends(get_db)):
    email = payload.get('email')
    if not email:
        raise HTTPException(status_code=400, detail='Email required')
    
    token = serializer.dumps(email)
    
    # FIX: Using PUBLIC_URL to match our config naming
    base_url = getattr(settings, "PUBLIC_URL", "http://localhost:8000")
    link = f"{base_url}/api/auth/verify?token={token}"
    
    email_body = f"""
        <h3>Welcome to {settings.BRAND_NAME}</h3>
        <p>Click the button below to sign in to your AI Website Audit dashboard:</p>
        <a href='{link}' style='background-color:#2563eb; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;'>Sign In to Dashboard</a>
        <p>If the button doesn't work, copy and paste this link: {link}</p>
    """
    
    await send_resend_email(email, f"{settings.BRAND_NAME} Sign-in Link", email_body)
    return {"message": "Verification email sent. Please check your inbox."}

@router.get('/api/auth/verify')
async def verify(token: str, db: Session = Depends(get_db)):
    try:
        email = serializer.loads(token, max_age=3600)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail='Link expired')
    except BadSignature:
        raise HTTPException(status_code=400, detail='Invalid token')
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.is_verified = True
        db.commit()
    
    # Redirect to the verify page with email to trigger frontend confirmation
    return RedirectResponse(url=f"/verify?email={email}")
