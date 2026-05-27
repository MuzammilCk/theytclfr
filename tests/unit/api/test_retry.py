import pytest
import uuid
from fastapi.testclient import TestClient
from ytclfr.api.main import app
from ytclfr.api.auth import require_auth
from ytclfr.db.session import get_db
from ytclfr.db.models.job import Job
from ytclfr.contracts.manifest import SignalManifest

client = TestClient(app)

def override_require_auth():
    return {"user_id": "test_user"}

app.dependency_overrides[require_auth] = override_require_auth

def test_retry_job_not_found(mocker):
    # Setup mock DB session
    mock_db = mocker.MagicMock()
    mock_db.query().filter().first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    
    job_id = str(uuid.uuid4())
    response = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert response.status_code == 404
    app.dependency_overrides.pop(get_db)

def test_retry_job_v1(mocker):
    job_id = uuid.uuid4()
    mock_job = mocker.MagicMock()
    mock_job.id = job_id
    mock_job.status = "failed"
    mock_job.s3_video_uri = None # V1 jobs lack this
    
    mock_db = mocker.MagicMock()
    mock_db.query().filter().first.return_value = mock_job
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # Mocking task invocation
    mock_task = mocker.patch("ytclfr.tasks.ingest.download_video.delay")
    
    response = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert response.status_code == 200
    mock_task.assert_called_once_with(str(job_id))
    assert response.json()["resumed_from"] == "download_video"
    app.dependency_overrides.pop(get_db)

def test_retry_job_v2_manifest_exists(mocker):
    job_id = uuid.uuid4()
    mock_job = mocker.MagicMock()
    mock_job.id = job_id
    mock_job.status = "failed"
    mock_job.s3_video_uri = "s3://bucket/video.mp4"
    
    mock_db = mocker.MagicMock()
    mock_db.query().filter().first.return_value = mock_job
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # Manifest exists
    mock_manifest = mocker.MagicMock()
    mocker.patch("ytclfr.storage.manifest_store.SignalManifestStore.get_by_job_id", return_value=mock_manifest)
    mocker.patch("ytclfr.storage.evidence_store.EvidenceGraphStore.get_by_job_id", return_value=None)
    
    mock_task = mocker.patch("ytclfr.tasks.stage_b.run_targeted_extraction.delay")
    
    response = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert response.status_code == 200
    mock_task.assert_called_once_with(str(job_id))
    assert response.json()["resumed_from"] == "run_targeted_extraction"
    app.dependency_overrides.pop(get_db)

def test_retry_job_v2_no_manifest(mocker):
    job_id = uuid.uuid4()
    mock_job = mocker.MagicMock()
    mock_job.id = job_id
    mock_job.status = "failed"
    mock_job.s3_video_uri = "s3://bucket/video.mp4"
    
    mock_db = mocker.MagicMock()
    mock_db.query().filter().first.return_value = mock_job
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # No manifest
    mocker.patch("ytclfr.storage.manifest_store.SignalManifestStore.get_by_job_id", return_value=None)
    
    mock_task = mocker.patch("ytclfr.tasks.stage_a.run_signal_census.delay")
    
    response = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert response.status_code == 200
    mock_task.assert_called_once_with(str(job_id))
    assert response.json()["resumed_from"] == "run_signal_census"
    app.dependency_overrides.pop(get_db)
