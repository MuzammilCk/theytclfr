"""Unit tests for Stage B SSE event contracts.

Validates StageBStatus, StageBEvent, and backward compatibility
with V1 (VideoIngestedEvent) and Stage A events.
"""

from ytclfr.contracts.events import StageBEvent, StageBStatus


class TestStageBEvents:
    """Tests for Stage B SSE event models."""

    def test_started_event_validates(self):
        """StageBEvent with STARTED type must validate."""
        event = StageBEvent(
            event_type=StageBStatus.STARTED,
            job_id="00000000-0000-0000-0000-000000000099",
        )
        assert event.event_type == StageBStatus.STARTED.value
        assert event.extractors_dispatched == []

    def test_dispatched_event_with_extractor_list(self):
        """DISPATCHED event carries extractors_dispatched list."""
        event = StageBEvent(
            event_type=StageBStatus.DISPATCHED,
            job_id="00000000-0000-0000-0000-000000000099",
            extractors_dispatched=["asr", "audio"],
        )
        assert "asr" in event.extractors_dispatched
        assert "audio" in event.extractors_dispatched

    def test_failed_event_carries_error(self):
        """FAILED event carries error string."""
        event = StageBEvent(
            event_type=StageBStatus.FAILED,
            job_id="00000000-0000-0000-0000-000000000099",
            error="test error",
        )
        assert event.error == "test error"

    def test_v1_ingestion_event_still_importable(self):
        """V1 VideoIngestedEvent must still import without error."""
        from ytclfr.contracts.events import VideoIngestedEvent

        assert VideoIngestedEvent is not None

    def test_stage_a_event_still_importable(self):
        """Stage A events must still import without error."""
        from ytclfr.contracts.events import (
            StageAEvent,
            StageAStatus,
        )

        assert StageAStatus.COMPLETE.value == "stage_a_complete"
        assert StageAEvent is not None
