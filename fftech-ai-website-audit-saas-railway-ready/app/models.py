from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from .db import Base

class Audit(Base):
    __tablename__ = 'audits'
    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    
    # Relaxed columns to prevent 500 errors
    status = Column(String(50), nullable=True, server_default=text("'completed'"))
    score = Column(Integer, nullable=True)
    grade = Column(String(5), nullable=True)
    coverage = Column(Float, nullable=True) # FIX: Prevents the latest crash
    
    result_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
