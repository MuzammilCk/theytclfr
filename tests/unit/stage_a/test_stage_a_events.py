"""Unit tests for Stage A SSE event contracts."""

from ytclfr.contracts.events import (
    StageAEvent,
    StageAStatus,
    VideoIngestedEvent,
)


class TestStageAEvents:
    """Tests for Stage A event types."""

    def test_started_event_validates(self) -> None:
        """StageAEvent with STARTED type must validate."""
        event = StageAEvent(
            event_type=StageAStatus.STARTED,
            job_id="00000000-0000-0000-0000-000000000099",
        )
        assert event.event_type == StageAStatus.STARTED.value

    def test_complete_event_with_manifest_id(self) -> None:
        """COMPLETE event with manifest_id validates."""
        event = StageAEvent(
            event_type=StageAStatus.COMPLETE,
            job_id="00000000-0000-0000-0000-000000000099",
            manifest_id="abc-123",
        )
        assert event.manifest_id == "abc-123"

    def test_failed_event_with_error(self) -> None:
        """FAILED event with error string validates."""
        event = StageAEvent(
            event_type=StageAStatus.FAILED,
            job_id="00000000-0000-0000-0000-000000000099",
            error="Something went wrong",
        )
        assert event.error == "Something went wrong"
        assert event.event_type == StageAStatus.FAILED.value

    def test_probe_complete_events_with_details(self) -> None:
        """Probe completion events with details dict validates."""
        event = StageAEvent(
            event_type=StageAStatus.PROBE_AUDIO_COMPLETE,
            job_id="00000000-0000-0000-0000-000000000099",
            details={
                "audio_type": "speech_only",
                "has_speech": True,
            },
        )
        assert event.details["audio_type"] == "speech_only"

    def test_v1_events_still_importable(self) -> None:
        """V1 event types must still import without error."""
        assert VideoIngestedEvent is not None

    def test_all_status_values_exist(self) -> None:
        """All expected StageAStatus enum values must exist."""
        expected = {
            "stage_a_started",
            "stage_a_probe_audio_complete",
            "stage_a_probe_visual_complete",
            "stage_a_probe_metadata_complete",
            "stage_a_complete",
            "stage_a_failed",
        }
        actual = {s.value for s in StageAStatus}
        assert actual == expected
