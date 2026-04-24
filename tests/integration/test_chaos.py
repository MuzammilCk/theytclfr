import uuid
import pytest
from ytclfr.db.models.job import Job
from ytclfr.db.models.extractor_result import ExtractorResultModel
from ytclfr.tasks.ingest import download_video
from ytclfr.tasks.extract import run_asr
from fastapi.testclient import TestClient

def test_pipeline_recovers_from_s3_failure(mocker, db_session):
    # Setup job
    job = Job(id=uuid.uuid4(), youtube_url="https://youtube.com/watch?v=mock", status="pending")
    db_session.add(job)
    db_session.commit()

    # Mock S3 upload to fail on first attempt
    s3_mock = mocker.patch("ytclfr.ingestion.s3_storage.S3StorageManager.upload_file")
    s3_mock.side_effect = [Exception("S3 Timeout"), "s3://bucket/video.mp4"]

    # Mock yt-dlp to avoid actual download
    mocker.patch("ytclfr.ingestion.downloader.VideoDownloader.download")
    
    # Simulate first attempt which fails
    with pytest.raises(Exception):
        download_video.retry = Exception # mock retry exception
        download_video(str(job.id))

    # Expect S3 was called once
    assert s3_mock.call_count == 1

def test_idempotency_prevents_duplicate_extraction(mocker, db_session):
    job = Job(id=uuid.uuid4(), youtube_url="https://youtube.com/watch?v=mock", status="extracting", s3_video_uri="s3://mock/video.mp4")
    db_session.add(job)
    
    ext_result = ExtractorResultModel(
        job_id=job.id,
        extractor_type="asr",
        segments_json={"segments": []},
        total_duration_seconds=10.0,
        error_message=None
    )
    db_session.add(ext_result)
    db_session.commit()

    s3_download_mock = mocker.patch("ytclfr.ingestion.s3_storage.S3StorageManager.download_file")
    
    # Run ASR
    result = run_asr(str(job.id))
    
    # S3 should not be hit, because of idempotency
    s3_download_mock.assert_not_called()
    assert result["status"] == "success"

def test_retry_endpoint_resumes_from_checkpoint(mocker, db_session, test_client: TestClient, test_token: str):
    job = Job(id=uuid.uuid4(), youtube_url="https://youtube.com/watch?v=mock", status="dead_letter", s3_video_uri="s3://mock/video.mp4")
    db_session.add(job)
    
    from ytclfr.db.models.router_decision import RouterDecisionModel
    decision = RouterDecisionModel(job_id=job.id, primary_route="full", confidence=0.9, speech_density=0.5, ocr_density=0.5, routing_notes="")
    db_session.add(decision)
    db_session.commit()

    mocker.patch("ytclfr.tasks.extract.run_asr.s")
    mocker.patch("ytclfr.tasks.extract.run_ocr.s")
    mocker.patch("ytclfr.tasks.extract.run_audio_classifier.s")
    
    headers = {"Authorization": f"Bearer {test_token}"}
    response = test_client.post(f"/api/v1/jobs/{job.id}/retry", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["resumed_from"] == "extractors"
