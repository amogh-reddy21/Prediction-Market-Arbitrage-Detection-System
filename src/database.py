"""Database connection and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from contextlib import contextmanager
from loguru import logger

Base = declarative_base()

# Engine is created lazily on first access so that DATABASE_URL is fully
# resolved (Railway / Render inject it at runtime, not at import time).
_engine = None
_Session = None


def get_engine():
    """Return the singleton SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is None:
        from .config import config  # imported here to avoid circular import
        _engine = create_engine(
            config.SQLALCHEMY_URI,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=config.FLASK_DEBUG,
        )
    return _engine


def get_session_factory():
    """Return the scoped session factory, creating it on first call."""
    global _Session
    if _Session is None:
        _Session = scoped_session(sessionmaker(bind=get_engine()))
    return _Session


@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    Session = get_session_factory()
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def test_connection():
    """Test database connectivity."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("✓ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False


def init_db():
    """Create all tables defined in models (idempotent)."""
    # Import models so their metadata is registered before create_all
    from . import models  # noqa: F401
    Base.metadata.create_all(get_engine())
    logger.info("✓ Database tables initialised")

