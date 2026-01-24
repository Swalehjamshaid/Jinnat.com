# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from .db import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class Audit(Base):
    __tablename__ = 'audits'
    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    status = Column(String(50), server_default="completed")
    score = Column(Integer, nullable=True)
    grade = Column(String(5), nullable=True)
    coverage = Column(Float, nullable=True)
    result_json = Column(JSONB, nullable=True)
    
    # FIX: This fills the date automatically so the DB doesn't crash
    created_at = Column(DateTime, server_default=func.now())
    
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
