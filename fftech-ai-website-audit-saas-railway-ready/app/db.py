import os
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

Base = declarative_base()

def _add_ssl_and_timeouts(db_url: str) -> str:
    """
    Cleans the URL and ensures it uses the correct PostgreSQL dialect and SSL.
    """
    if not db_url:
        raise ValueError("DATABASE_URL is missing. Set it in Railway → Variables.")

    # 1. REMOVE ACCIDENTAL QUOTES (Fixes the current crash)
    db_url = db_url.strip().strip('"').strip("'")

    # 2. Fix legacy 'postgres://' to 'postgresql://' for SQLAlchemy 2.0
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    parsed = urlparse(db_url)
    if "postgresql" in parsed.scheme:
        q = dict(parse_qsl(parsed.query))
        q.setdefault("sslmode", "require")
        q.setdefault("connect_timeout", "5")
        parsed = parsed._replace(query=urlencode(q))
        return urlunparse(parsed)

    return db_url

# Load and clean the URL from Environment Variables
raw_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = _add_ssl_and_timeouts(raw_url)

# Create engine with resilient pool settings
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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def try_connect_with_retries_and_create_tables(retries: int = 5, delay_seconds: float = 2.0):
    """
    Handles Railway database cold starts and ensures tables are created.
    """
    from . import models  # Import models so Base recognizes the tables
    
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[DB] Attempt {attempt}/{retries} connecting to database...")
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            
            print("[DB] Connection successful ✓")
            Base.metadata.create_all(bind=engine)
            print("[DB] Tables verified/created ✓")
            return

        except (OperationalError, Exception) as e:
            last_error = e
            if attempt < retries:
                print(f"[DB] Connection failed: {e}. Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)

    print("[DB] Critical: Could not connect to database.")
    raise last_error
