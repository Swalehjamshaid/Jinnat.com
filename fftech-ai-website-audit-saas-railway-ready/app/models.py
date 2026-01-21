from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    plan = Column(String(50), default='free')
    audit_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    token_expiry = Column(Integer, nullable=True)

    audits = relationship('Audit', back_populates='user')

class Audit(Base):
    __tablename__ = 'audits'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    url = Column(String(2048), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    result_json = Column(JSON)
    overall_score = Column(Integer, default=0)
    grade = Column(String(5), default='F')
    
    user = relationship('User', back_populates='audits')
