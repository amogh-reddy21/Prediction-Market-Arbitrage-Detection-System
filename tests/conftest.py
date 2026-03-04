"""
Shared pytest fixtures and test database setup.

This module patches src.database with an in-memory SQLite instance *once*
for the entire test session, before any src module is imported.  All test
modules that need DB access share the same engine and session factory.
"""

import sys
import types
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ---------------------------------------------------------------------------
# Build the in-memory engine and stub ONCE at collection time.
# Both test_integration.py and test_tracker.py will see the same stub because
# sys.modules is process-global and this file is loaded first by pytest.
# ---------------------------------------------------------------------------

TEST_ENGINE = create_engine('sqlite:///:memory:', echo=False)
TestSessionFactory = sessionmaker(bind=TEST_ENGINE)
TestSession = scoped_session(TestSessionFactory)

@event.listens_for(TEST_ENGINE, "connect")
def _enable_fk(dbapi_con, _):
    dbapi_con.execute("PRAGMA foreign_keys=ON")

_stub_base = declarative_base()

@contextmanager
def _test_db_session():
    session = TestSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

_stub = types.ModuleType('src.database')
_stub.engine = TEST_ENGINE
_stub.Session = TestSession
_stub.get_db_session = _test_db_session
_stub.Base = _stub_base
_stub.test_connection = lambda: True

# Inject before any src module is imported
if 'src.database' not in sys.modules:
    sys.modules['src.database'] = _stub

# Now import models so their classes are registered against _stub_base
from src.models import Base as ModelsBase  # noqa: E402 — must come after patch

# Create all tables once for the session
ModelsBase.metadata.create_all(TEST_ENGINE)
