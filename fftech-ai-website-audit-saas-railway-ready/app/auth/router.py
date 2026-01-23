from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import EmailStr
from sqlalchemy.orm import Session

# ABSOLUTE IMPORTS - Ensures consistency across Docker
from app.db import get_db
from app.models import User
from app.auth.tokens import create_token, decode_token
from app.auth.email import send_magic_link

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post('/request-link')
def request_link(email: EmailStr, db: Session = Depends(get_db)):
    email = email.lower()
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        user = User(email=email, is_verified=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        
    token = create_token(sub=email)
    send_magic_link(email, token)
    return {"message": "Magic link sent"}

@router.get('/magic')
def magic(token: str, response: Response, db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
        
    email = payload.get('sub')
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_verified = True
    db.commit()
    
    # Secure session handling
    response.set_cookie(
        key="session", 
        value=token, 
        httponly=True, 
        samesite='lax',
        secure=False  # Set to True in production with HTTPS
    )
    return RedirectResponse(url='/dashboard', status_code=302)
