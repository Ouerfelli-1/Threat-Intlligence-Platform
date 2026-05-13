"""
SQLAlchemy database connection manager for the TIP database.
Separate from the existing recon TimescaleDB instance.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

from tip.core.config import settings

Base = declarative_base()

engine = create_engine(
    settings.TIP_DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_all_tables():
    """Create all database tables from ORM models."""
    # Import models so they register with Base.metadata
    import tip.core.models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """Drop all database tables (use with caution)."""
    import tip.core.models  # noqa: F401
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager that provides a transactional database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
