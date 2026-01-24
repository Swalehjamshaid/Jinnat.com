# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base

# Enhanced JSON logic: JSONB for Railway (Postgres), Standard JSON for local (SQLite)
try:
    from sqlalchemy.dialects.postgresql import JSONB as PostgresJSON
    JSONType = PostgresJSON
except ImportError:
    from sqlalchemy import JSON
    JSONType = JSON

class User(Base):
    """Stores user account and subscription details."""
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    plan = Column(String(50), default='free')
    audit_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    
    audits = relationship('Audit', back_populates='user', cascade="all, delete-orphan")
    schedules = relationship('Schedule', back_populates='user', cascade="all, delete-orphan")

class Audit(Base):
    """Stores the complete results of a website audit."""
    __tablename__ = 'audits'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True) 
    url = Column(String(2048), nullable=False)
    
    # FIX 1: Allow null status to stop NotNullViolation
    status = Column(String(50), nullable=True, server_default=text("'completed'"))
    
    # FIX 2: Added score column as nullable. 
    # This prevents the DB from crashing when your code sends no score.
    score = Column(Integer, nullable=True) 
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Stores the huge dictionary from your runner/grader
    result_json = Column(JSONType, nullable=True)
    
    user = relationship('User', back_populates='audits')

class Schedule(Base):
    """Stores settings for recurring automated audits."""
    __tablename__ = 'schedules'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    url = Column(String(2048), nullable=False)
    cron = Column(String(50), default='@daily')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship('User', back_populates='schedules')
