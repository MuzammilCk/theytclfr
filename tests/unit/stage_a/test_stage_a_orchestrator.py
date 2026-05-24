"""Tests for ytclfr.tasks.stage_a.run_signal_census orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch
from uuid import UUID, uuid4

from ytclfr.contracts.events import StageAStatus
from ytclfr.probing.audio_checker import AudioProbeResult
from ytclfr.probing.frame_sampler import VisualProbeResult
from ytclfr.probing.metadata_probe import MetadataProbeResult
from ytclfr.tasks.stage_a import run_signal_census


# ── Helpers ──────────────────────────────────────────────────────────


def _make_mock_job(
    *,
    job_id: UUID | None = None,
    local_media_path: str | None = "/videos/test.mp4",
    s3_video_uri: str | None = None,
    metadata_raw: dict | None = None,
    status: str = "ingested",
) -> MagicMock:
    """Build a mock Job ORM object with the required attributes."""
    job = MagicMock()
    job.id = job_id or uuid4()
    job.local_media_path = local_media_path
    job.s3_video_uri = s3_video_uri
    job.metadata_raw = metadata_raw or {
        "duration": 120.0,
        "width": 1920,
        "height": 1080,
        "title": "Test Video",
    }
    job.status = status
    job.error_message = None
    return job


def _make_audio_result(**overrides: object) -> AudioProbeResult:
    defaults = dict(
        has_speech=True,
        has_music=False,
        audio_type="speech_only",
        language="en",
        duration_seconds=120.0,
        confidence=0.85,
    )
    defaults.update(overrides)
    return AudioProbeResult(**defaults)


def _make_visual_result(**overrides: object) -> VisualProbeResult:
    defaults = dict(
        has_faces=True,
        has_burned_in_text=False,
        motion_score=0.4,
        motion_density=2.5,
        scene_cut_count=5,
        aspect_ratio="16:9",
        content_format="live_action",
        frame_count_sampled=30,
        confidence=0.75,
    )
    defaults.update(overrides)
    return VisualProbeResult(**defaults)


def _make_metadata_result(**overrides: object) -> MetadataProbeResult:
    defaults = dict(
        duration_seconds=120.0,
        aspect_ratio="16:9",
        has_subtitle_track=False,
        has_auto_captions=True,
        language="en",
        has_chapters=False,
        chapter_count=0,
        tags=["test"],
        title="Test Video",
        upload_date="20250101",
        confidence=0.95,
    )
    defaults.update(overrides)
    return MetadataProbeResult(**defaults)


def _make_mock_temp_manager() -> MagicMock:
    """Create a mock TempStorageManager whose get_job_dir
    returns a Path-like object with / operator support."""
    mock_temp = MagicMock()
    mock_dir = MagicMock(spec=Path)
    mock_video_path = MagicMock(spec=Path)
    mock_video_path.__str__ = lambda self: "/tmp/job/video_probe.mp4"
    mock_video_path.exists.return_value = True
    mock_video_path.parent = MagicMock(spec=Path)

    def truediv(self_: object, other: str) -> MagicMock:
        return mock_video_path

    mock_dir.__truediv__ = truediv
    mock_temp.get_job_dir.return_value = mock_dir
    return mock_temp, mock_video_path


# ── Tests ────────────────────────────────────────────────────────────


def test_run_signal_census_happy_path_local():
    """Local media path exists → all probes succeed → returns ok."""
    job_uuid = uuid4()
    mock_job = _make_mock_job(job_id=job_uuid)

    with (
        patch("ytclfr.tasks.stage_a.get_settings"),
        patch("ytclfr.tasks.stage_a.db_session") as mock_db_session,
        patch("ytclfr.tasks.stage_a.probe_audio") as mock_probe_audio,
        patch("ytclfr.tasks.stage_a.probe_visual") as mock_probe_visual,
        patch(
            "ytclfr.tasks.stage_a.probe_metadata_dict"
        ) as mock_probe_meta,
        patch("ytclfr.tasks.stage_a._emit_sse"),
        patch("ytclfr.tasks.stage_a._manifest_store") as mock_store,
        patch("ytclfr.tasks.stage_a.os.path.exists", return_value=True),
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        mock_probe_audio.return_value = _make_audio_result()
        mock_probe_visual.return_value = _make_visual_result()
        mock_probe_meta.return_value = _make_metadata_result()

        mock_orm_manifest = MagicMock()
        mock_orm_manifest.id = uuid4()
        mock_store.create.return_value = mock_orm_manifest

        result = run_signal_census.apply(args=[str(job_uuid)])
        value = result.get()

        assert value["status"] == "ok"
        assert value["job_id"] == str(job_uuid)
        assert "manifest" in value

        mock_probe_audio.assert_called_once()
        mock_probe_visual.assert_called_once()
        mock_probe_meta.assert_called_once()
        mock_store.create.assert_called_once()
        mock_session.commit.assert_called()


def test_run_signal_census_s3_download_path():
    """local_media_path is None, s3_video_uri set → downloads from S3,
    probes, and cleans up transient file."""
    job_uuid = uuid4()
    mock_job = _make_mock_job(
        job_id=job_uuid,
        local_media_path=None,
        s3_video_uri="s3://bucket/video.mp4",
    )

    mock_temp, mock_video_path = _make_mock_temp_manager()

    with (
        patch("ytclfr.tasks.stage_a.get_settings"),
        patch("ytclfr.tasks.stage_a.db_session") as mock_db_session,
        patch("ytclfr.tasks.stage_a.probe_audio") as mock_probe_audio,
        patch("ytclfr.tasks.stage_a.probe_visual") as mock_probe_visual,
        patch(
            "ytclfr.tasks.stage_a.probe_metadata_dict"
        ) as mock_probe_meta,
        patch("ytclfr.tasks.stage_a._emit_sse"),
        patch("ytclfr.tasks.stage_a._manifest_store") as mock_store,
        patch(
            "ytclfr.tasks.stage_a.S3StorageManager"
        ) as mock_s3_cls,
        patch(
            "ytclfr.tasks.stage_a.TempStorageManager"
        ) as mock_temp_cls,
        patch("ytclfr.tasks.stage_a.os.path.exists", return_value=False),
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        mock_s3_cls.return_value = MagicMock()
        mock_temp_cls.return_value = mock_temp

        mock_probe_audio.return_value = _make_audio_result()
        mock_probe_visual.return_value = _make_visual_result()
        mock_probe_meta.return_value = _make_metadata_result()

        mock_orm_manifest = MagicMock()
        mock_orm_manifest.id = uuid4()
        mock_store.create.return_value = mock_orm_manifest

        result = run_signal_census.apply(args=[str(job_uuid)])
        value = result.get()

        assert value["status"] == "ok"
        # S3 download should have been invoked
        mock_s3_cls.return_value.download_file.assert_called_once()
        # Transient file should be cleaned up in finally
        mock_video_path.unlink.assert_called_once_with(missing_ok=True)


def test_run_signal_census_job_not_found():
    """No job in DB → raises ValueError and calls retry."""
    job_uuid = uuid4()

    with (
        patch("ytclfr.tasks.stage_a.get_settings"),
        patch("ytclfr.tasks.stage_a.db_session") as mock_db_session,
        patch("ytclfr.tasks.stage_a._emit_sse"),
        patch(
            "ytclfr.tasks.stage_a.run_signal_census.retry"
        ) as mock_retry,
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            None
        )

        mock_retry.side_effect = Exception("Retry called")

        try:
            run_signal_census.apply(args=[str(job_uuid)])
        except Exception:
            pass

        mock_retry.assert_called_once()


def test_run_signal_census_no_media_available():
    """Both local_media_path and s3_video_uri are None → raises ValueError."""
    job_uuid = uuid4()
    mock_job = _make_mock_job(
        job_id=job_uuid,
        local_media_path=None,
        s3_video_uri=None,
    )

    with (
        patch("ytclfr.tasks.stage_a.get_settings"),
        patch("ytclfr.tasks.stage_a.db_session") as mock_db_session,
        patch("ytclfr.tasks.stage_a._emit_sse") as mock_sse,
        patch(
            "ytclfr.tasks.stage_a.run_signal_census.retry"
        ) as mock_retry,
        patch("ytclfr.tasks.stage_a.os.path.exists", return_value=False),
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        mock_retry.side_effect = Exception("Retry called")

        try:
            run_signal_census.apply(args=[str(job_uuid)])
        except Exception:
            pass

        mock_retry.assert_called_once()
        # Should have emitted a FAILED SSE event
        sse_calls = mock_sse.call_args_list
        event_types = [
            c.args[0].event_type for c in sse_calls
        ]
        assert StageAStatus.FAILED.value in event_types


def test_run_signal_census_metadata_raw_is_none():
    """job.metadata_raw is None → skips metadata probe,
    still produces manifest with defaults."""
    job_uuid = uuid4()
    mock_job = _make_mock_job(job_id=job_uuid)
    mock_job.metadata_raw = None

    with (
        patch("ytclfr.tasks.stage_a.get_settings"),
        patch("ytclfr.tasks.stage_a.db_session") as mock_db_session,
        patch("ytclfr.tasks.stage_a.probe_audio") as mock_probe_audio,
        patch("ytclfr.tasks.stage_a.probe_visual") as mock_probe_visual,
        patch(
            "ytclfr.tasks.stage_a.probe_metadata_dict"
        ) as mock_probe_meta,
        patch("ytclfr.tasks.stage_a._emit_sse"),
        patch("ytclfr.tasks.stage_a._manifest_store") as mock_store,
        patch("ytclfr.tasks.stage_a.os.path.exists", return_value=True),
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        mock_probe_audio.return_value = _make_audio_result()
        mock_probe_visual.return_value = _make_visual_result()

        mock_orm_manifest = MagicMock()
        mock_orm_manifest.id = uuid4()
        mock_store.create.return_value = mock_orm_manifest

        result = run_signal_census.apply(args=[str(job_uuid)])
        value = result.get()

        assert value["status"] == "ok"
        # probe_metadata_dict should NOT have been called
        mock_probe_meta.assert_not_called()
        # Manifest should still be created
        mock_store.create.assert_called_once()


def test_run_signal_census_transient_cleanup_on_failure():
    """S3 download path + probe failure → finally block
    still cleans up transient file."""
    job_uuid = uuid4()
    mock_job = _make_mock_job(
        job_id=job_uuid,
        local_media_path=None,
        s3_video_uri="s3://bucket/video.mp4",
    )

    mock_temp, mock_video_path = _make_mock_temp_manager()

    with (
        patch("ytclfr.tasks.stage_a.get_settings"),
        patch("ytclfr.tasks.stage_a.db_session") as mock_db_session,
        patch("ytclfr.tasks.stage_a.probe_audio") as mock_probe_audio,
        patch("ytclfr.tasks.stage_a.probe_visual"),
        patch("ytclfr.tasks.stage_a.probe_metadata_dict"),
        patch("ytclfr.tasks.stage_a._emit_sse"),
        patch("ytclfr.tasks.stage_a._manifest_store"),
        patch(
            "ytclfr.tasks.stage_a.S3StorageManager"
        ) as mock_s3_cls,
        patch(
            "ytclfr.tasks.stage_a.TempStorageManager"
        ) as mock_temp_cls,
        patch("ytclfr.tasks.stage_a.os.path.exists", return_value=False),
        patch(
            "ytclfr.tasks.stage_a.run_signal_census.retry"
        ) as mock_retry,
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        mock_s3_cls.return_value = MagicMock()
        mock_temp_cls.return_value = mock_temp

        # probe_audio explodes
        mock_probe_audio.side_effect = RuntimeError("Probe crashed")
        mock_retry.side_effect = Exception("Retry called")

        try:
            run_signal_census.apply(args=[str(job_uuid)])
        except Exception:
            pass

        # Transient file must still be cleaned up even on failure
        mock_video_path.unlink.assert_called_once_with(missing_ok=True)


def test_run_signal_census_sets_job_status():
    """Verifies job.status transitions from stage_a_running → stage_a_complete."""
    job_uuid = uuid4()
    mock_job = _make_mock_job(job_id=job_uuid, status="ingested")

    # Track status changes in order
    status_changes: list[str] = []
    original_status = mock_job.status

    def track_status(val: str) -> None:
        status_changes.append(val)

    type(mock_job).status = property(
        lambda self: status_changes[-1] if status_changes else original_status,
        lambda self, v: track_status(v),
    )

    with (
        patch("ytclfr.tasks.stage_a.get_settings"),
        patch("ytclfr.tasks.stage_a.db_session") as mock_db_session,
        patch("ytclfr.tasks.stage_a.probe_audio") as mock_probe_audio,
        patch("ytclfr.tasks.stage_a.probe_visual") as mock_probe_visual,
        patch(
            "ytclfr.tasks.stage_a.probe_metadata_dict"
        ) as mock_probe_meta,
        patch("ytclfr.tasks.stage_a._emit_sse"),
        patch("ytclfr.tasks.stage_a._manifest_store") as mock_store,
        patch("ytclfr.tasks.stage_a.os.path.exists", return_value=True),
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        mock_probe_audio.return_value = _make_audio_result()
        mock_probe_visual.return_value = _make_visual_result()
        mock_probe_meta.return_value = _make_metadata_result()

        mock_orm_manifest = MagicMock()
        mock_orm_manifest.id = uuid4()
        mock_store.create.return_value = mock_orm_manifest

        result = run_signal_census.apply(args=[str(job_uuid)])
        result.get()

        assert "stage_a_running" in status_changes
        assert "stage_a_complete" in status_changes
        # running must come before complete
        assert status_changes.index("stage_a_running") < status_changes.index(
            "stage_a_complete"
        )


def test_run_signal_census_emits_sse_events():
    """Verifies _emit_sse is called with correct event types in order."""
    job_uuid = uuid4()
    mock_job = _make_mock_job(job_id=job_uuid)

    with (
        patch("ytclfr.tasks.stage_a.get_settings"),
        patch("ytclfr.tasks.stage_a.db_session") as mock_db_session,
        patch("ytclfr.tasks.stage_a.probe_audio") as mock_probe_audio,
        patch("ytclfr.tasks.stage_a.probe_visual") as mock_probe_visual,
        patch(
            "ytclfr.tasks.stage_a.probe_metadata_dict"
        ) as mock_probe_meta,
        patch("ytclfr.tasks.stage_a._emit_sse") as mock_sse,
        patch("ytclfr.tasks.stage_a._manifest_store") as mock_store,
        patch("ytclfr.tasks.stage_a.os.path.exists", return_value=True),
    ):
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_job
        )

        mock_probe_audio.return_value = _make_audio_result()
        mock_probe_visual.return_value = _make_visual_result()
        mock_probe_meta.return_value = _make_metadata_result()

        mock_orm_manifest = MagicMock()
        mock_orm_manifest.id = uuid4()
        mock_store.create.return_value = mock_orm_manifest

        result = run_signal_census.apply(args=[str(job_uuid)])
        result.get()

        # Collect the event types from all _emit_sse calls
        emitted_types = [
            c.args[0].event_type for c in mock_sse.call_args_list
        ]

        # Must emit at least: STARTED, PROBE_METADATA_COMPLETE,
        # PROBE_AUDIO_COMPLETE, PROBE_VISUAL_COMPLETE, COMPLETE
        assert StageAStatus.STARTED.value in emitted_types
        assert StageAStatus.PROBE_METADATA_COMPLETE.value in emitted_types
        assert StageAStatus.PROBE_AUDIO_COMPLETE.value in emitted_types
        assert StageAStatus.PROBE_VISUAL_COMPLETE.value in emitted_types
        assert StageAStatus.COMPLETE.value in emitted_types

        # STARTED must be first
        assert emitted_types[0] == StageAStatus.STARTED.value
        # COMPLETE must be last
        assert emitted_types[-1] == StageAStatus.COMPLETE.value
