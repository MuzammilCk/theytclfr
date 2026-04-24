from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from ytclfr.tasks.extract import run_asr, run_audio_classifier, run_ocr


def _make_mock_temp_manager() -> MagicMock:
    """Create a mock TempStorageManager whose get_job_dir
    returns a Path-like object with / operator support."""
    mock_temp = MagicMock()
    mock_dir = MagicMock(spec=Path)
    # Path / "video.mp4" returns a Path-like mock
    mock_video_path = MagicMock(spec=Path)
    mock_video_path.exists.return_value = False
    mock_video_path.parent = MagicMock(spec=Path)

    mock_frames_dir = MagicMock(spec=Path)
    mock_frames_dir.exists.return_value = False

    def truediv(self_: object, other: str) -> MagicMock:
        if other == "video.mp4":
            return mock_video_path
        return mock_frames_dir

    mock_dir.__truediv__ = truediv
    mock_temp.get_job_dir.return_value = mock_dir
    return mock_temp


def test_run_asr_calls_asr_extractor_and_persists_result():
    job_uuid = uuid4()
    with (
        patch("ytclfr.tasks.extract.get_settings"),
        patch("ytclfr.tasks.extract.db_session") as mock_db_session,
        patch("ytclfr.extractors.asr.get_asr_extractor") as mock_get_asr,
        patch(
            "ytclfr.ingestion.s3_storage.S3StorageManager"
        ) as mock_s3_cls,
        patch(
            "ytclfr.tasks.extract.TempStorageManager"
        ) as mock_temp_cls,
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        mock_job = MagicMock()
        mock_job.s3_video_uri = "s3://test-bucket/video.mp4"
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        # Mock S3 download (no-op)
        mock_s3_cls.return_value = MagicMock()

        # Mock temp manager
        mock_temp_cls.return_value = _make_mock_temp_manager()

        mock_extractor = MagicMock()
        mock_get_asr.return_value = mock_extractor

        mock_result = MagicMock()
        mock_result.segments = []
        mock_result.model_dump.return_value = {}
        mock_extractor.extract.return_value = mock_result

        run_asr.apply(args=[str(job_uuid)])

        mock_extractor.extract.assert_called_once()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


def test_run_ocr_calls_ocr_extractor_and_persists_result():
    job_uuid = uuid4()
    with (
        patch("ytclfr.tasks.extract.get_settings"),
        patch("ytclfr.tasks.extract.db_session") as mock_db_session,
        patch(
            "ytclfr.ingestion.s3_storage.S3StorageManager"
        ) as mock_s3_cls,
        patch(
            "ytclfr.tasks.extract.TempStorageManager"
        ) as mock_temp_cls,
        patch("ytclfr.extractors.ocr.get_ocr_extractor") as mock_get_ocr,
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        mock_job = MagicMock()
        mock_job.s3_video_uri = "s3://test-bucket/video.mp4"
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        # Mock S3 download (no-op)
        mock_s3_cls.return_value = MagicMock()

        # Mock temp manager
        mock_temp_cls.return_value = _make_mock_temp_manager()

        mock_extractor = MagicMock()
        mock_get_ocr.return_value = mock_extractor

        mock_result = MagicMock()
        mock_result.segments = []
        mock_result.model_dump.return_value = {}
        mock_extractor.extract.return_value = mock_result

        run_ocr.apply(args=[str(job_uuid)])

        mock_extractor.extract.assert_called_once()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


def test_run_asr_retries_on_unexpected_exception():
    job_uuid = uuid4()
    with (
        patch("ytclfr.tasks.extract.get_settings"),
        patch("ytclfr.tasks.extract.db_session") as mock_db_session,
        patch("ytclfr.extractors.asr.get_asr_extractor") as mock_get_asr,
        patch("ytclfr.tasks.extract.run_asr.retry") as mock_retry,
        patch(
            "ytclfr.ingestion.s3_storage.S3StorageManager"
        ) as mock_s3_cls,
        patch(
            "ytclfr.tasks.extract.TempStorageManager"
        ) as mock_temp_cls,
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        mock_job = MagicMock()
        mock_job.s3_video_uri = "s3://test-bucket/video.mp4"
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        # Mock S3 download (no-op)
        mock_s3_cls.return_value = MagicMock()

        # Mock temp manager
        mock_temp_cls.return_value = _make_mock_temp_manager()

        mock_extractor = MagicMock()
        mock_get_asr.return_value = mock_extractor

        mock_extractor.extract.side_effect = RuntimeError("Something bad")

        mock_retry.side_effect = Exception("Retry called")

        try:
            run_asr.apply(args=[str(job_uuid)])
        except Exception:
            pass

        mock_retry.assert_called_once()


def test_run_audio_classifier_uses_job_metadata():
    job_uuid = uuid4()
    with (
        patch("ytclfr.tasks.extract.db_session") as mock_db_session,
        patch(
            "ytclfr.extractors.audio_classifier.classify_audio_from_metadata"
        ) as mock_classify,
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session

        mock_job = MagicMock()
        meta = {"acodec": "aac"}
        mock_job.metadata_raw = meta
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        mock_result = MagicMock()
        mock_result.segments = []
        mock_result.model_dump.return_value = {}
        mock_classify.return_value = mock_result

        run_audio_classifier.apply(args=[str(job_uuid)])

        mock_classify.assert_called_once_with(
            job_id=job_uuid, metadata_raw=meta
        )
