import logging
from typing import Generator
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from stockguard.config import get_settings

logger = logging.getLogger("stockguard.database")
settings = get_settings()

_engine: Engine | None = None
_active_db_url: str = ""


def get_engine() -> Engine:
    global _engine, _active_db_url
    if _engine is not None:
        return _engine

    target_url = settings.DATABASE_URL
    try:
        if "postgresql" in target_url:
            test_engine = create_engine(
                target_url,
                pool_pre_ping=True,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                echo=settings.DB_ECHO,
                connect_args={"connect_timeout": 3},
            )
            # Verify connectivity
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connected successfully to PostgreSQL: %s", target_url.split("@")[-1])
            _engine = test_engine
            _active_db_url = target_url
            return _engine
    except Exception as e:
        logger.warning(
            "Primary database (%s) unavailable (%s). Falling back to %s",
            target_url.split("@")[-1] if "@" in target_url else target_url,
            e,
            settings.FALLBACK_DATABASE_URL,
        )

    # Fallback to SQLite (or test database)
    _active_db_url = settings.FALLBACK_DATABASE_URL
    connect_args = {}
    if "sqlite" in _active_db_url:
        connect_args = {"check_same_thread": False}

    _engine = create_engine(_active_db_url, echo=settings.DB_ECHO, connect_args=connect_args)

    if "sqlite" in _active_db_url:
        # Enable foreign keys and WAL mode for SQLite
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    logger.info("Database initialized using: %s", _active_db_url)
    return _engine


def get_session_factory():
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_active_db_url() -> str:
    get_engine()
    return _active_db_url


def is_postgresql() -> bool:
    return "postgresql" in get_active_db_url()
