import time
from datetime import UTC
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt

from ytclfr.api.auth import decode_supabase_jwt
from ytclfr.api.main import app
from ytclfr.core.config import Settings
from ytclfr.db.session import get_db

TEST_SECRET = "test_secret_key_for_unit_tests_only"
TEST_ALGORITHM = "HS256"


def make_test_token(
    sub: str = "test_user",
    secret: str = TEST_SECRET,
    expired: bool = False,
) -> str:
    payload = {
        "sub": sub,
        "iat": int(time.time()),
        "exp": int(time.time()) + (-60 if expired else 3600),
        "jti": "test-jti-001",
    }
    return jwt.encode(payload, secret, algorithm=TEST_ALGORITHM)


@pytest.fixture
def mock_settings():
    return Settings(
        database_url="sqlite://",
        redis_url="redis://",
        groq_api_key="fake",
        jwt_secret_key=TEST_SECRET,
        jwt_algorithm=TEST_ALGORITHM,
    )


@patch("ytclfr.api.auth.get_settings")
def test_valid_token_returns_payload(mock_get_settings, mock_settings):
    mock_get_settings.return_value = mock_settings
    token = make_test_token()
    payload = decode_supabase_jwt(token)
    assert payload["sub"] == "test_user"


@patch("ytclfr.api.auth.get_settings")
def test_expired_token_raises_401(mock_get_settings, mock_settings):
    mock_get_settings.return_value = mock_settings
    token = make_test_token(expired=True)
    with pytest.raises(HTTPException) as exc:
        decode_supabase_jwt(token)
    assert exc.value.status_code == 401


@patch("ytclfr.api.auth.get_settings")
def test_wrong_secret_raises_401(mock_get_settings, mock_settings):
    mock_settings.jwt_secret_key = "wrong_secret"
    mock_get_settings.return_value = mock_settings
    token = make_test_token(secret=TEST_SECRET)
    with pytest.raises(HTTPException) as exc:
        decode_supabase_jwt(token)
    assert exc.value.status_code == 401


@patch("ytclfr.api.auth.get_settings")
def test_malformed_token_raises_401(mock_get_settings, mock_settings):
    mock_get_settings.return_value = mock_settings
    with pytest.raises(HTTPException) as exc:
        decode_supabase_jwt("not.a.jwt")
    assert exc.value.status_code == 401


@patch("ytclfr.api.auth.get_settings")
def test_empty_token_raises_401(mock_get_settings, mock_settings):
    mock_get_settings.return_value = mock_settings
    with pytest.raises(HTTPException) as exc:
        decode_supabase_jwt("")
    assert exc.value.status_code == 401


@patch("ytclfr.api.auth.get_settings")
@patch("ytclfr.api.v1.jobs.download_video.delay")
def test_require_auth_with_valid_token(mock_delay, mock_get_settings, mock_settings):
    mock_get_settings.return_value = mock_settings

    mock_db = MagicMock()

    def mock_refresh(job):
        import uuid
        from datetime import datetime
        job.id = uuid.uuid4()
        job.created_at = datetime.now(UTC)

    mock_db.refresh.side_effect = mock_refresh
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    token = make_test_token()
    response = client.post(
        "/api/v1/jobs",
        json={"youtube_url": "https://www.youtube.com/watch?v=12345678910"},
        headers={"Authorization": f"Bearer {token}"},
    )

    app.dependency_overrides.clear()

    assert response.status_code != 401
    assert response.status_code != 403


def test_require_auth_missing_header_returns_401():
    client = TestClient(app)
    response = client.post(
        "/api/v1/jobs", json={"youtube_url": "https://youtube.com/watch?v=12345"}
    )
    assert response.status_code == 401


def test_require_auth_invalid_token_returns_401():
    client = TestClient(app)
    response = client.post(
        "/api/v1/jobs",
        json={"youtube_url": "https://youtube.com/watch?v=12345"},
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert response.status_code == 401


def test_health_endpoint_requires_no_auth():
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
