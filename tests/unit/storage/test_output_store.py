import uuid
from unittest.mock import MagicMock
from datetime import datetime, timezone
from ytclfr.contracts.alignment import AlignedTimeline, AlignedSegment
from ytclfr.storage.output_store import assemble_and_save_final_output
from ytclfr.db.models.router_decision import RouterDecisionModel
from ytclfr.db.models.final_output import FinalOutputModel

def test_assemble_and_save_final_output(mocker):
    mock_session = MagicMock()
    mock_router_decision = MagicMock(primary_route="speech-heavy")
    
    # Setup the mock query chain
    mock_query = mock_session.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_filter.first.side_effect = [mock_router_decision, None, None] # router_decision, job, existing output
    
    job_id = uuid.uuid4()
    timeline = AlignedTimeline(
        job_id=job_id,
        segments=[
            AlignedSegment(timestamp=0.0, end_timestamp=1.0, text="hello world", source="asr", confidence=0.9, original_segment_ids=["1"])
        ],
        total_segments=1,
        has_gaps=False,
        aligned_at=datetime.now(timezone.utc)
    )
    
    output = assemble_and_save_final_output(job_id, timeline, {"overall_score": 0.95}, mock_session)
    
    assert output.content_type == "script"
    assert output.confidence == 0.95
    assert len(output.script) == 1
    assert output.script[0].text == "hello world"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
