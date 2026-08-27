from ytclfr.contracts.events import (
    StageCEvent, StageCStatus,
    StageAStatus, StageAEvent,
    StageBStatus, StageBEvent,
    VideoIngestedEvent,
)


class TestStageCEvents:

    def test_started_event_validates(self):
        """StageCEvent with STARTED validates."""
        event = StageCEvent(
            event_type=StageCStatus.STARTED,
            job_id="00000000-0000-0000-0000-000000000099",
        )
        assert event.event_type == StageCStatus.STARTED.value

    def test_complete_event_with_graph_id(self):
        """COMPLETE event carries evidence_graph_id."""
        event = StageCEvent(
            event_type=StageCStatus.COMPLETE,
            job_id="00000000-0000-0000-0000-000000000099",
            evidence_graph_id="some-uuid",
        )
        assert event.evidence_graph_id == "some-uuid"

    def test_groq_skipped_event_validates(self):
        """GROQ_SKIPPED event validates without details."""
        event = StageCEvent(
            event_type=StageCStatus.GROQ_SKIPPED,
            job_id="00000000-0000-0000-0000-000000000099",
        )
        assert event.event_type == StageCStatus.GROQ_SKIPPED.value

    def test_failed_event_carries_error(self):
        """FAILED event carries error string."""
        event = StageCEvent(
            event_type=StageCStatus.FAILED,
            job_id="00000000-0000-0000-0000-000000000099",
            error="something broke",
        )
        assert event.error == "something broke"

    def test_all_prior_events_still_importable(self):
        """All V1 and Stage A/B events still import correctly."""
        assert VideoIngestedEvent is not None
        assert StageAStatus.COMPLETE.value == "stage_a_complete"
        assert StageBStatus.DISPATCHED.value == "stage_b_dispatched"

    def test_stage_c_status_has_seven_values(self):
        """StageCStatus enum has exactly 7 values."""
        values = {s.value for s in StageCStatus}
        assert len(values) == 7
