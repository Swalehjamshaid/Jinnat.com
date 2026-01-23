from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db import Base

class User(Base):
    """
    Standard User model for Professional Access.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    """
    ISO-Standard Audit Log for tracking website audits and errors.
    This resolves the ImportError in your router.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True, nullable=False)
    
    # Audit Results
    status = Column(String)  # SUCCESS, WARNING, FAILURE
    error_code = Column(String, nullable=True) # e.g., SSL_001, NET_404
    performance_score = Column(Float, default=0.0)
    
    # Metadata for ISO 25010 Efficiency tracking
    execution_time = Column(Float) # In seconds
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Flexible JSON storage for the full world-class report
    raw_data = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<AuditLog(url={self.url}, status={self.status})>"
