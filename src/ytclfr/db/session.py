import typing
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from ytclfr.core.config import get_settings
from ytclfr.db.base import SessionLocal, build_engine

_engine = None


def _get_engine() -> typing.Any:
    """Build and cache the SQLAlchemy engine.

    Binds SessionLocal exactly once — on first call.
    Subsequent calls return the cached engine without
    reconfiguring the session factory.
    """
    global _engine
    if _engine is None:
        _engine = build_engine(get_settings())
        # Bind once here — never again in get_db() or db_session().
        SessionLocal.configure(bind=_engine)
    return _engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a database session.

    Ensures engine is initialized on first call.
    Closes the session in the finally block.
    """
    _get_engine()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for use in Celery tasks and scripts.

    Use this in all Celery tasks instead of get_db().
    Ensures engine is initialized on first call.
    Closes the session in the finally block.
    """
    _get_engine()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
