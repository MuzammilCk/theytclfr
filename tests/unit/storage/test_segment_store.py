import uuid
from unittest.mock import MagicMock
from ytclfr.contracts.alignment import AlignedTimeline, AlignedSegment
from ytclfr.core.config import Settings
from ytclfr.storage.segment_store import save_aligned_segments
from ytclfr.db.models.aligned_segment import AlignedSegmentModel

def test_save_aligned_segments(mocker):
    mock_session = MagicMock()
    settings = Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        groq_api_key="test",
        jwt_secret_key="test"
    )
    
    mocker.patch("ytclfr.storage.segment_store.generate_embeddings_batch", return_value=[[0.1]*768])
    
    job_id = uuid.uuid4()
    timeline = AlignedTimeline(
        segments=[
            AlignedSegment(start_seconds=0.0, end_seconds=1.0, text="test", source="asr", confidence=0.9)
        ],
        total_segments=1,
        has_gaps=False
    )
    
    count = save_aligned_segments(job_id, timeline, settings, mock_session)
    assert count == 1
    mock_session.add_all.assert_called_once()
    mock_session.commit.assert_called_once()
