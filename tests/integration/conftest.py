"""Shared fixtures for integration tests.

Provides db_session, test_client, test_token, and setup_test_db fixtures
that are automatically available to all test modules under tests/integration/.

All fixtures are skipped when TEST_DATABASE_URL is not set.
"""

import os
import time

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ytclfr.api.main import app
from ytclfr.db.session import get_db

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL environment variable is not set",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Database engine & session factory
# ---------------------------------------------------------------------------
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
TEST_JWT_SECRET = "integration_test_secret"
TEST_JWT_ALGORITHM = "HS256"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Run Alembic migrations before the test session and tear down after."""
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["JWT_SECRET_KEY"] = TEST_JWT_SECRET
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield

    command.downgrade(alembic_cfg, "base")
    engine.dispose()


@pytest.fixture
def db_session():
    """Yield a fresh SQLAlchemy session, closed automatically after the test."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_client():
    """Return a FastAPI TestClient with the DB dependency overridden."""
    return TestClient(app)


@pytest.fixture
def test_token():
    """Return a valid JWT bearer token for authenticated endpoints."""
    payload = {
        "sub": "integration_test_user",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": "integration-test-jti",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)
