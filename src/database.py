"""Database connection and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from contextlib import contextmanager
from loguru import logger

from .config import config

# SQLAlchemy Base
Base = declarative_base()

# Engine
engine = create_engine(
    config.MYSQL_URI,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=config.FLASK_DEBUG
)

# Session factory
SessionFactory = sessionmaker(bind=engine)
Session = scoped_session(SessionFactory)

@contextmanager
def get_db_session():
    """Context manager for database sessions."""
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
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("✓ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False

def init_db():
    """Initialize database tables (if needed beyond schema.sql)."""
    Base.metadata.create_all(engine)
    logger.info("Database tables initialized")
