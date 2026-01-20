import os
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from .config import settings  # Make sure settings.DATABASE_URL exists for fallback

Base = declarative_base()

# ───────────────────────────────────────────────
# Add SSL and connect timeout for Railway
# ───────────────────────────────────────────────
def _add_ssl_and_timeouts(db_url: str) -> str:
    if not db_url:
        raise ValueError("DATABASE_URL is missing. Ensure Postgres is linked in Railway.")

    # Debug
    print(f"[DB DEBUG] Raw input URL: {db_url}")

    # Remove quotes/whitespace
    db_url = db_url.strip().strip('"').strip("'")
    print(f"[DB DEBUG] After cleaning: {db_url}")

    parsed = urlparse(db_url)
    if parsed.scheme.startswith("postgres"):
        query_params = dict(parse_qsl(parsed.query))
        query_params.setdefault("sslmode", "require")
        query_params.setdefault("connect_timeout", "5")
        parsed = parsed._replace(query=urlencode(query_params))
        final_url = urlunparse(parsed)
        print(f"[DB DEBUG] Final URL with SSL: {final_url}")
        return final_url
    return db_url

# ───────────────────────────────────────────────
# Get DATABASE_URL
# ───────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

print(f"[DB DEBUG] os.getenv('DATABASE_URL'): {DATABASE_URL}")

# Fallback to settings.py
if not DATABASE_URL:
    print("[DB DEBUG] No env var – falling back to settings.DATABASE_URL")
    DATABASE_URL = settings.DATABASE_URL

# Final check
if not DATABASE_URL or DATABASE_URL == "postgresql://postgres:OyukiGQaJmjLuEiXSOizUEMleaTLBjtj@":
    raise ValueError(
        "No valid DATABASE_URL found. Make sure host, port, and database name are included."
    )

# Add SSL and timeouts
DATABASE_URL = _add_ssl_and_timeouts(DATABASE_URL)

# ───────────────────────────────────────────────
# SQLAlchemy engine
# ───────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    future=True,
)

# ───────────────────────────────────────────────
# Session factory
# ───────────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

# ───────────────────────────────────────────────
# FastAPI dependency
# ───────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ───────────────────────────────────────────────
# Retry connection and create tables
# ───────────────────────────────────────────────
def try_connect_with_retries_and_create_tables(
    retries: int = 5, delay_seconds: float = 2.0
):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[DB] Attempt {attempt}/{retries} connecting to database...")
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[DB] Connection successful ✓")

            # Import models to create tables
            from . import models  # noqa: F401

            print("[DB] Creating tables (if not exist)...")
            Base.metadata.create_all(bind=engine)
            print("[DB] Tables created ✓")
            return
        except OperationalError as e:
            last_error = e
            if attempt < retries:
                print(
                    f"[DB] Connection failed: {e}. Retrying in {delay_seconds}s..."
                )
                time.sleep(delay_seconds)
    raise last_error or Exception("Database connection failed after retries")


# ───────────────────────────────────────────────
# Initialize DB on startup
# ───────────────────────────────────────────────
try_connect_with_retries_and_create_tables()
