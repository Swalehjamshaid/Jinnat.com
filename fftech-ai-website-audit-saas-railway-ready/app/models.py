from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from .db import Base

# ADD THIS: The missing users table
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)

class Audit(Base):
    __tablename__ = 'audits'
    id = Column(Integer, primary_key=True)
    url = Column(String(2048), nullable=False)
    status = Column(String(50), nullable=True)
    score = Column(Integer, nullable=True)
    grade = Column(String(5), nullable=True)
    coverage = Column(Float, nullable=True)
    result_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    # This links to the User class above
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
