import uuid
from unittest.mock import MagicMock
from ytclfr.storage.queries import (
    get_final_output_by_job_id,
    get_segments_by_time_range,
    search_segments_by_keyword,
    search_segments_by_similarity
)

def test_get_final_output_by_job_id():
    mock_session = MagicMock()
    mock_model = MagicMock()
    mock_model.output_json = {
        "job_id": str(uuid.uuid4()),
        "content_type": "script",
        "video_metadata": {"title": "test"},
        "confidence": 0.9,
        "provenance": [{"source": "asr"}],
        "processed_at": "2026-04-24T00:00:00Z",
        "processing_duration_seconds": 10.0,
        "items": [],
        "script": []
    }
    mock_session.query.return_value.filter.return_value.first.return_value = mock_model
    
    output = get_final_output_by_job_id(uuid.uuid4(), mock_session)
    assert output is not None
    assert output.content_type == "script"

def test_get_segments_by_time_range():
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    
    segs = get_segments_by_time_range(uuid.uuid4(), 0.0, 10.0, mock_session)
    assert isinstance(segs, list)

def test_search_segments_by_keyword():
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    
    segs = search_segments_by_keyword(uuid.uuid4(), "test", mock_session)
    assert isinstance(segs, list)

def test_search_segments_by_similarity():
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    
    segs = search_segments_by_similarity(uuid.uuid4(), [0.1]*768, mock_session)
    assert isinstance(segs, list)
