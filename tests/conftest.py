import sys
import os
import pytest
from starlette.testclient import TestClient
from sqlalchemy import text

# Ensure src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from stockguard.main import app
from stockguard.database import get_engine, get_session_factory
from stockguard.models import init_db, Base


@pytest.fixture(scope="session")
def engine():
    eng = get_engine()
    init_db(eng)
    return eng


@pytest.fixture(scope="function")
def db_session(engine):
    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(engine):
    with TestClient(app) as c:
        yield c
