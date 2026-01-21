import os
from typing import Optional
from pydantic import BaseSettings, Field, PostgresDsn, validator

class Settings(BaseSettings):
    """
    Application configuration using Pydantic BaseSettings (Pydantic v1 compatible).
    Loads from environment variables and .env file.
    """

    # ── APP IDENTITY & BRANDING ──────────────────────────────────────────────
    BRAND_NAME: str = Field(default="FF Tech", env="BRAND_NAME")
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "AI-Powered Website Audit SaaS"

    # ── SERVER & URL CONFIG ──────────────────────────────────────────────────
    PUBLIC_URL: str = Field(
        default="http://localhost:8000",
        env="PUBLIC_URL",
        description="Base URL of the deployed app (used for magic links, etc.)"
    )
    SECRET_KEY: str = Field(
        default="FF_TECH_SUPER_SECRET_TOKEN_2026",
        env="SECRET_KEY",
        min_length=32,
        description="Used for JWT signing and other crypto operations"
    )

    # ── DATABASE ─────────────────────────────────────────────────────────────
    DATABASE_URL: PostgresDsn = Field(..., env="DATABASE_URL")
    # Optional: allow SQLite fallback for local dev (not recommended in prod)
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @validator("SQLALCHEMY_DATABASE_URI", always=True)
    def set_sqlalchemy_uri(cls, v, values):
        return values.get("DATABASE_URL")

    # ── EMAIL (Passwordless Auth via Resend) ─────────────────────────────────
    RESEND_API_KEY: str = Field(..., env="RESEND_API_KEY")
    EMAIL_FROM: str = Field(
        default="no-reply@fftech.com",
        env="EMAIL_FROM",
        description="Sender email for magic links"
    )
    EMAIL_FROM_NAME: str = Field(default="FF Tech", env="EMAIL_FROM_NAME")

    # ── AI (Gemini for summaries, insights, executive reports) ───────────────
    GEMINI_API_KEY: str = Field(..., env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")

    # ── AUDIT & USER LIMITS ──────────────────────────────────────────────────
    AUDIT_LIMIT_FREE: int = Field(default=10, env="AUDIT_LIMIT_FREE")
    AUDIT_HISTORY_RETENTION_DAYS: int = Field(default=30, env="AUDIT_HISTORY_RETENTION_DAYS")
    PREMIUM_AUDIT_LIMIT: int = Field(default=500, env="PREMIUM_AUDIT_LIMIT")

    # ── STORAGE & REPORTS ────────────────────────────────────────────────────
    REPORT_DIR: str = Field(
        default="storage/reports",
        env="REPORT_DIR",
        description="Where generated PDF reports are stored (Railway volume)"
    )
    EXPORT_DIR: str = Field(default="storage/exports", env="EXPORT_DIR")

    # ── SECURITY & JWT ───────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    # ── CRAWLER & AUDIT SETTINGS ─────────────────────────────────────────────
    MAX_CRAWL_DEPTH: int = 5
    MAX_PAGES_TO_CRAWL: int = 200
    USER_AGENT: str = "FFTech-AI-Auditor/1.0 (+https://fftech.com/bot)"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # Usually better to be case-insensitive
        validate_all = True


# Singleton instance
settings = Settings()

# Quick validation on startup (useful for Railway)
if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL is required but not set")
if not settings.RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY is required for passwordless authentication")
if not settings.GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is required for AI summaries")
