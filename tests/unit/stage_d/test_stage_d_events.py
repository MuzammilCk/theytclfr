from ytclfr.contracts.events import (
    StageDEvent, StageDStatus,
    StageCStatus, StageBStatus, StageAStatus,
    VideoIngestedEvent,
)


class TestStageDEvents:

    def test_started_event_validates(self):
        """StageDEvent with STARTED validates."""
        event = StageDEvent(
            event_type=StageDStatus.STARTED,
            job_id="00000000-0000-0000-0000-000000000099",
        )
        assert event.event_type == StageDStatus.STARTED.value

    def test_complete_event_with_taxonomy(self):
        """COMPLETE event carries taxonomy dict."""
        event = StageDEvent(
            event_type=StageDStatus.COMPLETE,
            job_id="00000000-0000-0000-0000-000000000099",
            taxonomy={"parent": "Education", "child": "Tutorial"},
        )
        assert event.taxonomy["parent"] == "Education"

    def test_groq_skipped_event_validates(self):
        """GROQ_TAXONOMY_SKIPPED validates without taxonomy."""
        event = StageDEvent(
            event_type=StageDStatus.GROQ_TAXONOMY_SKIPPED,
            job_id="00000000-0000-0000-0000-000000000099",
        )
        assert event.taxonomy == {}

    def test_failed_event_with_error(self):
        """FAILED event carries error string."""
        event = StageDEvent(
            event_type=StageDStatus.FAILED,
            job_id="00000000-0000-0000-0000-000000000099",
            error="database connection failed",
        )
        assert event.error == "database connection failed"

    def test_stage_d_status_has_six_values(self):
        """StageDStatus has exactly 6 values."""
        assert len(list(StageDStatus)) == 6

    def test_all_prior_events_still_importable(self):
        """All V1 and Stage A/B/C events still import."""
        assert VideoIngestedEvent is not None
        assert StageAStatus.COMPLETE.value == "stage_a_complete"
        assert StageBStatus.DISPATCHED.value == "stage_b_dispatched"
        assert StageCStatus.COMPLETE.value == "stage_c_complete"
