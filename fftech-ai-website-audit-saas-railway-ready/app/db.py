# app/db.py
import os
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

Base = declarative_base()

def _add_ssl_and_timeouts(db_url: str) -> str:
    """
    Cleans the URL, fixes the dialect, and forces a remote connection.
    """
    # 1. Check if the URL is actually there
    if not db_url or len(db_url) < 10:
        print("\n!!! CRITICAL ERROR !!!")
        print("DATABASE_URL is empty or invalid in Railway Variables.")
        print("Go to Railway -> Variables -> Add DATABASE_URL")
        print("!!!!!!!!!!!!!!!!!!!!!!!\n")
        # Returning a dummy remote URL prevents the local 'socket' error
        return "postgresql://missing_user:missing_pass@invalid_host:5432/missing_db"

    # 2. Strip quotes and spaces
    db_url = db_url.strip().strip('"').strip("'")

    # 3. Fix dialect for SQLAlchemy 2.0
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # 4. Add SSL and connection params
    parsed = urlparse(db_url)
    q = dict(parse_qsl(parsed.query))
    q.setdefault("sslmode", "require")
    q.setdefault("connect_timeout", "10")
    parsed = parsed._replace(query=urlencode(q))
    
    return urlunparse(parsed)

# Load the URL
raw_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = _add_ssl_and_timeouts(raw_url)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def try_connect_with_retries_and_create_tables(retries: int = 5, delay_seconds: float = 5.0):
    # Ensure models are imported so tables are created
    from . import models 
    
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[DB] Attempt {attempt}/{retries} connecting to remote host...")
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            
            print("[DB] Connection successful ✓")
            Base.metadata.create_all(bind=engine)
            print("[DB] Tables verified ✓")
            return 

        except Exception as e:
            last_error = e
            print(f"[DB] Attempt {attempt} failed: {str(e)}")
            if attempt < retries:
                time.sleep(delay_seconds)

    print("[DB] PANIC: Could not connect to the remote database.")
    raise last_error
