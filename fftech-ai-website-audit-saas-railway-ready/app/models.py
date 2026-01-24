# app/models.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from datetime import datetime
from .db import Base

# Choose the best JSON storage type based on the database engine
try:
    JSONType = JSONB # Optimized for PostgreSQL (Railway)
except Exception:
    JSONType = SQLITE_JSON # Fallback for SQLite (Local)

class User(Base):
    """Stores user account and subscription details."""
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    plan = Column(String(50), default='free') # Tracks 'free' vs 'premium'
    audit_count = Column(Integer, default=0) # Limits users based on their plan
    is_verified = Column(Boolean, default=False)
    
    # Relationships connect tables together
    audits = relationship('Audit', back_populates='user')
    schedules = relationship('Schedule', back_populates='user')

class Audit(Base):
    """Stores the complete results of a website audit."""
    __tablename__ = 'audits'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    url = Column(String(2048), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # result_json holds the final data from grader.py (scores, breakdowns)
    result_json = Column(JSONType)
    
    user = relationship('User', back_populates='audits')

class Schedule(Base):
    """Stores settings for recurring automated audits."""
    __tablename__ = 'schedules'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    url = Column(String(2048), nullable=False)
    cron = Column(String(50), default='@daily') # e.g., 'every day'
    is_active = Column(Boolean, default=True)
    
    user = relationship('User', back_populates='schedules')
