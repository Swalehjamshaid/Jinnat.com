from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
import jwt
from datetime import datetime, timedelta

from ..db import get_db
from ..models import User
from ..schemas import UserCreate, UserLogin
from ..config import settings
from ..utils.security import hash_password, verify_password

router = APIRouter(prefix='/auth', tags=['auth'])

SESSION_COOKIE = 'session'
COOKIE_MAX_AGE = 60*60*24*14  # 14 days

@router.post('/signup')
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(400, 'Email already registered')
    p_hash, salt = hash_password(payload.password)
    user = User(email=payload.email, password_hash=p_hash, password_salt=salt)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {'id': user.id, 'email': user.email, 'is_paid': user.is_paid}

@router.post('/login')
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_salt, user.password_hash):
        raise HTTPException(401, 'Invalid credentials')
    token = jwt.encode({'sub': str(user.id), 'exp': datetime.utcnow() + timedelta(seconds=COOKIE_MAX_AGE)}, settings.SECRET_KEY, algorithm=settings.JWT_ALG)
    response.set_cookie(SESSION_COOKIE, token, max_age=COOKIE_MAX_AGE, httponly=True, samesite='lax', path='/')
    return {'ok': True}

@router.post('/logout')
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path='/')
    return {'ok': True}
