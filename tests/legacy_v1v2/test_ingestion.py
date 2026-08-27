import uuid
from unittest.mock import patch

import pytest

from ytclfr.db.models.job import Job

# Rely on global fixtures setup_test_db and db_session from conftest.py



@patch("ytclfr.api.v1.jobs.download_video.delay")
def test_submit_job_creates_db_record(mock_delay, db_session, test_client):
    response = test_client.post(
        "/api/v1/jobs",
        json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcW"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"

    job = db_session.query(Job).filter(Job.id == uuid.UUID(data["job_id"])).first()
    assert job is not None
    assert job.status == "pending"
    assert job.youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcW"

    mock_delay.assert_called_once_with(data["job_id"])


def test_job_status_returns_pending(db_session, test_client):
    job = Job(
        youtube_url="https://www.youtube.com/watch?v=abcdefghijk", status="pending"
    )  # noqa: E501
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = test_client.get(f"/api/v1/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == str(job.id)
    assert data["status"] == "pending"


def test_job_status_404_on_missing(test_client):
    random_id = uuid.uuid4()
    response = test_client.get(f"/api/v1/jobs/{random_id}")
    assert response.status_code == 404


def test_health_endpoint(test_client):
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
