from typing import Generator
from contextlib import contextmanager
from sqlalchemy.orm import Session
from ytclfr.core.config import get_settings
from ytclfr.db.base import build_engine, SessionLocal

_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        _engine = build_engine(get_settings())
    return _engine

def get_db() -> Generator[Session, None, None]:
    engine = _get_engine()
    SessionLocal.configure(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@contextmanager
def db_session() -> Generator[Session, None, None]:
    engine = _get_engine()
    SessionLocal.configure(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
