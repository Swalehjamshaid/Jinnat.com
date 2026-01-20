from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    is_paid = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    audits = relationship("Audit", back_populates="owner")

class Audit(Base):
    __tablename__ = "audits"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) 
    url = Column(String, nullable=False)
    score = Column(Integer)
    grade = Column(String(5))
    metrics = Column(JSON, nullable=True) # Stores all Categories A-I
    summary = Column(Text, nullable=True) 
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="audits")
