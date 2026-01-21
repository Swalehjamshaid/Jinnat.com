import logging
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

from .config import settings

logger = logging.getLogger(__name__)

# ── Database Engine ──────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,              # Detect broken connections
    pool_size=5,                     # Reasonable for Railway
    max_overflow=10,
    pool_timeout=30,
    echo=settings.get("DB_ECHO", False)  # Set DB_ECHO=true in .env for debug
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for all models
Base = declarative_base()


def get_db():
    """
    FastAPI dependency to provide DB session.
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(drop_all: bool = False):
    """
    Initialize database schema.
    
    WARNING: drop_all=True will DELETE ALL DATA — use only in dev/testing!
    """
    try:
        # Import all models so they register with Base.metadata
        from . import models  # noqa: F401

        if drop_all:
            logger.warning("Dropping all tables! This will delete all data.")
            Base.metadata.drop_all(bind=engine)

        logger.info("Creating database tables if they don't exist...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully.")

    except SQLAlchemyError as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during DB init: {str(e)}")
        raise


# Optional: helper for local dev (call manually if needed)
def reset_db():
    """Dangerous: Drops and recreates all tables — wipes all data!"""
    init_db(drop_all=True)


# Optional: shutdown hook (call on app shutdown if needed)
def dispose_engine():
    """Dispose engine connections (good practice on shutdown)"""
    engine.dispose()
    logger.info("Database engine disposed.")
