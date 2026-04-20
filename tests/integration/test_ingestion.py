import os
import uuid
from unittest.mock import patch

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from ytclfr.api.main import app
from ytclfr.db.models.job import Job
from ytclfr.db.session import get_db

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL environment variable is not set", allow_module_level=True
    )  # noqa: E501

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Upgrade
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield

    # Downgrade
    command.downgrade(alembic_cfg, "base")
    # Clean up connections
    engine.dispose()


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@patch("ytclfr.api.v1.jobs.download_video.delay")
def test_submit_job_creates_db_record(mock_delay, db_session):
    response = client.post(
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


def test_job_status_returns_pending(db_session):
    job = Job(
        youtube_url="https://www.youtube.com/watch?v=abcdefghijk", status="pending"
    )  # noqa: E501
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.get(f"/api/v1/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == str(job.id)
    assert data["status"] == "pending"


def test_job_status_404_on_missing():
    random_id = uuid.uuid4()
    response = client.get(f"/api/v1/jobs/{random_id}")
    assert response.status_code == 404


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
