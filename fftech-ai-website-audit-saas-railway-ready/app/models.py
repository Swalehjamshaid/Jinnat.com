from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Float,
    Index, Text
)
from sqlalchemy.orm import relationship, declared_attr
from sqlalchemy.sql import func

from .database import Base


class TimestampMixin:
    """Mixin to add automatic created/updated timestamps"""
    created_at = Column(DateTime, nullable=False, server_default=func.utcnow(), index=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.utcnow(),
        onupdate=func.utcnow(),
        index=True
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_subscribed = Column(Boolean, default=False, nullable=False)  # premium flag
    subscription_plan = Column(String(50), default="free")  # e.g. "free", "pro", "enterprise"
    subscription_expires_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    audits = relationship("Audit", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")

    # Convenience properties
    @property
    def audit_count(self) -> int:
        """Total audits performed by this user"""
        return len(self.audits) if self.audits else 0

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', verified={self.is_verified}, subscribed={self.is_subscribed})>"


class Audit(Base, TimestampMixin):
    __tablename__ = "audits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    url = Column(String(2048), nullable=False, index=True)
    status = Column(String(50), default="completed", nullable=False)  # pending, running, failed, completed
    overall_score = Column(Float, default=0.0, nullable=False)
    grade = Column(String(5), default="D", nullable=False)  # A+, A, B, C, D, F
    summary = Column(JSON, default=dict, nullable=False)
    metrics = Column(JSON, default=dict, nullable=False)
    category_scores = Column(JSON, default=dict, nullable=False)
    report_pdf_path = Column(String(512), nullable=True)
    competitors = Column(JSON, default=list, nullable=False)  # list of competitor URLs
    competitors_scores = Column(JSON, default=dict, nullable=False)

    # Relationships
    user = relationship("User", back_populates="audits")

    __table_args__ = (
        Index("ix_audit_user_url", "user_id", "url"),
        Index("ix_audit_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Audit(id={self.id}, url='{self.url}', grade='{self.grade}', score={self.overall_score})>"


class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String(2048), nullable=False, index=True)
    cron = Column(String(100), nullable=False)  # e.g. "0 0 * * *" for daily at midnight
    active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    notification_email = Column(String(255), nullable=True)  # optional override

    # Relationships
    user = relationship("User", back_populates="schedules")

    def __repr__(self):
        return f"<Schedule(id={self.id}, url='{self.url}', active={self.active}, cron='{self.cron}')>"
