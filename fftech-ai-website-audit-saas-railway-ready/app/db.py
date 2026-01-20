import os
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

Base = declarative_base()

def normalize_database_url(db_url: str) -> str:
    if not db_url:
        raise ValueError("DATABASE_URL is missing.")
    db_url = db_url.strip().strip('"').strip("'")
    parsed = urlparse(db_url)
    query = dict(parse_qsl(parsed.query))
    query.setdefault("sslmode", "require")
    query.setdefault("connect_timeout", "5")
    parsed = parsed._replace(query=urlencode(query))
    return urlunparse(parsed)

DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def try_connect_with_retries_and_create_tables():
    for attempt in range(1, 6):
        try:
            from . import models
            Base.metadata.create_all(bind=engine)
            return True
        except OperationalError:
            time.sleep(2)
    return False
