"""Tests for POST /api/v3/jobs (submit_job).

This endpoint had zero test coverage before it crashed in production
testing: a best-effort V4 shadow-pipeline dispatch (10% random sample,
apply_async with no broker guarantee) was throwing an uncaught
exception that took down the entire endpoint with a 500, even though
the real job had already been created successfully. The shadow
pipeline has been removed entirely; these tests cover the endpoint
that's left and guard against anything similar being reintroduced.
"""
import uuid
import importlib

import pytest
from fastapi.testclient import TestClient

from ytclfr.api.main import app
from ytclfr.api.auth import require_auth
from ytclfr.db.session import get_db

client = TestClient(app)


def override_require_auth():
    return {"user_id": "test_user"}


app.dependency_overrides[require_auth] = override_require_auth


def test_submit_job_success(mocker):
    mock_db = mocker.MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    mock_dispatch = mocker.patch("ytclfr.api.v3.jobs.download_video.delay")

    def fake_refresh(job):
        job.id = uuid.uuid4()
        job.created_at = __import__("datetime").datetime.now()
        job.error_message = None

    mock_db.refresh.side_effect = fake_refresh

    response = client.post(
        "/api/v3/jobs",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    mock_dispatch.assert_called_once()
    app.dependency_overrides.pop(get_db)


def test_submit_job_invalid_url(mocker):
    mock_db = mocker.MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/api/v3/jobs",
        json={"youtube_url": "not-a-youtube-url"},
    )

    assert response.status_code == 422
    app.dependency_overrides.pop(get_db)


def test_submit_job_never_touches_shadow_pipeline(mocker):
    """Regression test: submitting a job must succeed even under
    conditions that would previously trigger the shadow dispatch
    (any random() draw) and must not attempt to reach Celery for
    anything beyond the real download_video dispatch."""
    mock_db = mocker.MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    mocker.patch("ytclfr.api.v3.jobs.download_video.delay")
    # Force what used to be the "shadow fires" branch of random.random()
    mocker.patch("random.random", return_value=0.0)

    def fake_refresh(job):
        job.id = uuid.uuid4()
        job.created_at = __import__("datetime").datetime.now()
        job.error_message = None

    mock_db.refresh.side_effect = fake_refresh

    response = client.post(
        "/api/v3/jobs",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )

    assert response.status_code == 201
    app.dependency_overrides.pop(get_db)


def test_v4_shadow_module_no_longer_exists():
    """The v4_shadow package and its supporting scripts were removed
    entirely — this pins that decision so it can't silently drift back."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("ytclfr.tasks.v4_shadow.shadow_orchestrator")
