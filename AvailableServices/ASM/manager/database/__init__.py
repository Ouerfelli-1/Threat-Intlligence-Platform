"""
Database initialization and session management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# Database configuration - use DATABASE_URL from docker-compose or construct from parts
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    # Fallback to individual env vars
    db_user = os.getenv('POSTGRES_USER', 'recon')
    db_pass = os.getenv('POSTGRES_PASSWORD', 'changeme')
    db_host = os.getenv('POSTGRES_HOST', 'database')
    db_name = os.getenv('POSTGRES_DB', 'recon_manager')
    DATABASE_URL = f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"

engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db():
    """Database session context manager for services"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_db_session() -> Session:
    """FastAPI dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
