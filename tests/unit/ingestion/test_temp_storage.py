import time
import uuid

import pytest

from ytclfr.core.config import Settings
from ytclfr.ingestion.temp_storage import TempStorageManager


@pytest.fixture
def mock_settings(tmp_path):
    return Settings(
        database_url="sqlite://",
        redis_url="redis://",
        groq_api_key="fake",
        jwt_secret_key="fake",
        temp_media_path=str(tmp_path / "media"),
        temp_media_max_age_seconds=1,
    )


def test_get_job_dir_creates_directory(mock_settings):
    manager = TempStorageManager(mock_settings)
    job_id = uuid.uuid4()
    job_dir = manager.get_job_dir(job_id)
    assert job_dir.exists()
    assert job_dir.is_dir()


def test_get_job_dir_is_idempotent(mock_settings):
    manager = TempStorageManager(mock_settings)
    job_id = uuid.uuid4()
    job_dir1 = manager.get_job_dir(job_id)
    job_dir2 = manager.get_job_dir(job_id)
    assert job_dir1 == job_dir2


def test_cleanup_job_deletes_directory(mock_settings):
    manager = TempStorageManager(mock_settings)
    job_id = uuid.uuid4()
    job_dir = manager.get_job_dir(job_id)
    file = job_dir / "test.txt"
    file.touch()
    manager.cleanup_job(job_id)
    assert not job_dir.exists()


def test_cleanup_job_missing_directory_does_not_raise(mock_settings):
    manager = TempStorageManager(mock_settings)
    manager.cleanup_job(uuid.uuid4())


def test_cleanup_expired(mock_settings):
    manager = TempStorageManager(mock_settings)
    job_id_old = uuid.uuid4()
    job_id_new = uuid.uuid4()

    dir_old = manager.get_job_dir(job_id_old)
    time.sleep(1.1)
    dir_new = manager.get_job_dir(job_id_new)

    count = manager.cleanup_expired()

    assert count == 1
    assert not dir_old.exists()
    assert dir_new.exists()
