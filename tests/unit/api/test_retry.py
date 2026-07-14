import pytest
import uuid
from fastapi.testclient import TestClient
from ytclfr.api.main import app
from ytclfr.api.auth import require_auth
from ytclfr.db.session import get_db

client = TestClient(app)

def override_require_auth():
    return {"user_id": "test_user"}

app.dependency_overrides[require_auth] = override_require_auth

def test_retry_job_not_found(mocker):
    mock_db = mocker.MagicMock()
    mock_db.query().filter().first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    
    job_id = str(uuid.uuid4())
    response = client.post(f"/api/v3/jobs/{job_id}/retry")
    assert response.status_code == 404
    app.dependency_overrides.pop(get_db)

def test_retry_job_no_video(mocker):
    job_id = uuid.uuid4()
    mock_job = mocker.MagicMock()
    mock_job.id = job_id
    mock_job.status = "failed"
    mock_job.s3_video_uri = None 
    
    mock_db = mocker.MagicMock()
    mock_db.query().filter().first.return_value = mock_job
    app.dependency_overrides[get_db] = lambda: mock_db
    
    mock_task = mocker.patch("ytclfr.tasks.ingest.download_video.delay")
    
    response = client.post(f"/api/v3/jobs/{job_id}/retry")
    assert response.status_code == 200
    mock_task.assert_called_once_with(str(job_id), pipeline_version="v3")
    assert response.json()["resumed_from"] == "download_video"
    app.dependency_overrides.pop(get_db)

def test_retry_job_no_manifest(mocker):
    job_id = uuid.uuid4()
    mock_job = mocker.MagicMock()
    mock_job.id = job_id
    mock_job.status = "failed"
    mock_job.s3_video_uri = "s3://bucket/video.mp4"
    
    mock_db = mocker.MagicMock()
    # Mocking the job query to return the job
    mock_db.query().filter().first.return_value = mock_job
    app.dependency_overrides[get_db] = lambda: mock_db
    
    mocker.patch("ytclfr.storage.manifest_store.SignalManifestStore.get_by_job_id", return_value=None)
    
    mock_task = mocker.patch("ytclfr.tasks.v3.stage_a_census.v3_run_signal_census.delay")
    
    response = client.post(f"/api/v3/jobs/{job_id}/retry")
    assert response.status_code == 200
    mock_task.assert_called_once_with(str(job_id))
    assert response.json()["resumed_from"] == "stage_a_census"
    app.dependency_overrides.pop(get_db)

def test_retry_job_no_evidence(mocker):
    job_id = uuid.uuid4()
    mock_job = mocker.MagicMock()
    mock_job.id = job_id
    mock_job.status = "failed"
    mock_job.s3_video_uri = "s3://bucket/video.mp4"
    
    mock_db = mocker.MagicMock()
    
    # We need db.query to return the job for the first call, and None for the V3EvidenceGraphORM call
    def mock_query(model):
        q = mocker.MagicMock()
        if model.__name__ == "Job":
            q.filter().first.return_value = mock_job
        elif model.__name__ == "V3EvidenceGraphORM":
            q.filter().first.return_value = None
        return q
        
    mock_db.query = mock_query
    app.dependency_overrides[get_db] = lambda: mock_db
    
    mock_manifest = mocker.MagicMock()
    mocker.patch("ytclfr.storage.manifest_store.SignalManifestStore.get_by_job_id", return_value=mock_manifest)
    
    mock_task = mocker.patch("ytclfr.tasks.v3.stage_b_extraction.v3_run_targeted_extraction.delay")
    
    response = client.post(f"/api/v3/jobs/{job_id}/retry")
    assert response.status_code == 200
    mock_task.assert_called_once_with(str(job_id))
    assert response.json()["resumed_from"] == "stage_b_extraction"
    app.dependency_overrides.pop(get_db)

def test_retry_job_evidence_exists(mocker):
    job_id = uuid.uuid4()
    mock_job = mocker.MagicMock()
    mock_job.id = job_id
    mock_job.status = "failed"
    mock_job.s3_video_uri = "s3://bucket/video.mp4"
    
    mock_db = mocker.MagicMock()
    
    def mock_query(model):
        q = mocker.MagicMock()
        if model.__name__ == "Job":
            q.filter().first.return_value = mock_job
        elif model.__name__ == "V3EvidenceGraphORM":
            q.filter().first.return_value = mocker.MagicMock()
        return q
        
    mock_db.query = mock_query
    app.dependency_overrides[get_db] = lambda: mock_db
    
    mock_manifest = mocker.MagicMock()
    mocker.patch("ytclfr.storage.manifest_store.SignalManifestStore.get_by_job_id", return_value=mock_manifest)
    
    mock_task = mocker.patch("ytclfr.tasks.v3.stage_d_taxonomy.v3_run_taxonomy_mapping.delay")
    
    response = client.post(f"/api/v3/jobs/{job_id}/retry")
    assert response.status_code == 200
    mock_task.assert_called_once_with(str(job_id))
    assert response.json()["resumed_from"] == "stage_d_taxonomy"
    app.dependency_overrides.pop(get_db)
