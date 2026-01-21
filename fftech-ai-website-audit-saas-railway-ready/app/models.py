
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from datetime import datetime
from .db import Base
try:
    from sqlalchemy.dialects.postgresql import JSONB as JSONType
except Exception:
    JSONType = SQLITE_JSON

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    plan = Column(String(50), default='free')
    audit_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    audits = relationship('Audit', back_populates='user')
    schedules = relationship('Schedule', back_populates='user')

class Audit(Base):
    __tablename__ = 'audits'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    url = Column(String(2048), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    result_json = Column(JSONType)
    user = relationship('User', back_populates='audits')

class Schedule(Base):
    __tablename__ = 'schedules'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    url = Column(String(2048), nullable=False)
    cron = Column(String(50), default='@daily')
    is_active = Column(Boolean, default=True)
    user = relationship('User', back_populates='schedules')
