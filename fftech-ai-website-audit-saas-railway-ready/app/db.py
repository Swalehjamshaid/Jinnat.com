import os
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

Base = declarative_base()

# -------------------------------------------------
# Validate & Normalize DATABASE_URL (Railway Safe)
# -------------------------------------------------
def normalize_database_url(db_url: str) -> str:
    if not db_url:
        raise ValueError(
            "DATABASE_URL is missing. "
            "Link PostgreSQL in Railway and use the auto-generated DATABASE_URL."
        )

    print(f"[DB DEBUG] Raw DATABASE_URL: {db_url}")

    # Remove quotes and spaces
    db_url = db_url.strip().strip('"').strip("'")

    parsed = urlparse(db_url)

    # 🚨 Reject placeholder values immediately
    if any(x in db_url for x in ["username", "password", "hostname", "dbname"]):
        raise ValueError(
            "Invalid DATABASE_URL detected (placeholder values found). "
            "Replace DATABASE_URL with the real Railway PostgreSQL URL."
        )

    # 🚨 Force TCP connection (prevents Unix socket usage)
    if not parsed.hostname or not parsed.port or not parsed.path:
        raise ValueError(
            f"Invalid DATABASE_URL: {db_url}\n"
            "Railway DATABASE_URL must include hostname, port, and database name."
        )

    # Ensure SSL + timeout
    query = dict(parse_qsl(parsed.query))
    query.setdefault("sslmode", "require")
    query.setdefault("connect_timeout", "5")

    parsed = parsed._replace(query=urlencode(query))
    final_url = urlunparse(parsed)

    print(f"[DB DEBUG] Final DATABASE_URL: {final_url}")
    return final_url


# -------------------------------------------------
# Load DATABASE_URL (Railway first)
# -------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

print(f"[DB DEBUG] os.getenv('DATABASE_URL'): {DATABASE_URL}")

DATABASE_URL = normalize_database_url(DATABASE_URL)

# -------------------------------------------------
# SQLAlchemy Engine
# -------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


# -------------------------------------------------
# Dependency
# -------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------
# Startup Check + Auto Table Creation
# -------------------------------------------------
def try_connect_with_retries_and_create_tables(
    retries: int = 5,
    delay_seconds: float = 2.0,
):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            print(f"[DB] Attempt {attempt}/{retries} connecting to database...")
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[DB] Connection successful ✓")

            from . import models  # noqa: F401
            print("[DB] Creating tables (if not exist)...")
            Base.metadata.create_all(bind=engine)
            print("[DB] Tables created ✓")

            return

        except OperationalError as e:
            last_error = e
            print(f"[DB] Connection failed: {e}")
            if attempt < retries:
                print(f"[DB] Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)

    raise RuntimeError(
        "Database connection failed after retries. "
        "Check Railway Postgres status and DATABASE_URL."
    ) from last_error
