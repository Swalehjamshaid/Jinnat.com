import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status, Response
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import jwt
import httpx

from ..config import settings
from ..database import get_db  # assuming you have this dependency now
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

logger = logging.getLogger(__name__)

# Serializer for magic link tokens
magic_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

# JWT for session after verification
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # not used directly here


class EmailRequest(BaseModel):
    email: EmailStr


class AuthResponse(BaseModel):
    message: str
    access_token: Optional[str] = None


async def send_magic_link(email: str, token: str):
    """Send magic link email via Resend"""
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — email not sent")
        return

    base_url = settings.PUBLIC_URL.rstrip("/")
    verify_link = f"{base_url}/api/auth/verify?token={token}"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #2563eb;">Welcome to {settings.BRAND_NAME}</h2>
        <p>You're just one click away from your AI Website Audit dashboard.</p>
        <p style="margin: 30px 0;">
            <a href="{verify_link}" 
               style="background-color: #2563eb; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Sign In Now
            </a>
        </p>
        <p style="color: #64748b; font-size: 14px;">
            This link expires in 15 minutes for security. 
            If you didn't request this, ignore this email.
        </p>
        <p style="color: #64748b; font-size: 12px; margin-top: 40px;">
            {settings.BRAND_NAME} – AI-Powered Website Audits<br>
            {base_url}
        </p>
    </body>
    </html>
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": f"{settings.BRAND_NAME} <{settings.EMAIL_FROM}>",
                    "to": [email],
                    "subject": f"Login to {settings.BRAND_NAME}",
                    "html": html_content,
                }
            )
            resp.raise_for_status()
            logger.info(f"Magic link sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {str(e)}")


@router.post("/request-link", response_model=AuthResponse)
async def request_magic_link(payload: EmailRequest, db: Session = Depends(get_db)):
    """
    Send passwordless magic link to email
    """
    email = payload.email.lower().strip()

    # Optional: rate-limit per IP/email in production

    token = magic_serializer.dumps(email)

    await send_magic_link(email, token)

    # Create or update user early (pre-verification)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, is_verified=False)
        db.add(user)
        db.commit()
        db.refresh(user)

    return {"message": "Magic link sent to your email"}


@router.get("/verify", response_model=AuthResponse)
async def verify_magic_link(
    token: str,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Verify magic link token and issue JWT session
    """
    try:
        email = magic_serializer.loads(token, max_age=settings.MAGIC_LINK_EXPIRE_MINUTES * 60)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Link has expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid link")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark as verified
    user.is_verified = True
    db.commit()

    # Generate long-lived JWT access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = jwt.encode(
        {
            "sub": user.email,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + access_token_expires,
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    # Option 1: Redirect with token in query (simple, but less secure)
    # return RedirectResponse(url=f"/dashboard?token={access_token}")

    # Option 2: Set as cookie (recommended for security)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,              # only HTTPS in prod
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return RedirectResponse(url="/dashboard")


@router.post("/logout")
async def logout(response: Response):
    """Clear session cookie"""
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}
