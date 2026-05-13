"""
Database session dependency for FastAPI
"""
from sqlalchemy.orm import Session
from typing import Generator


def get_db() -> Generator[Session, None, None]:
    """Provide database session for FastAPI dependency injection"""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
