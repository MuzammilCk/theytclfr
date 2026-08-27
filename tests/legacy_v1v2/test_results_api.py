import pytest
from fastapi.testclient import TestClient
import uuid
from ytclfr.api.main import app
from ytclfr.api.auth import require_auth

client = TestClient(app)

def override_require_auth():
    return {"user_id": "test_user"}

app.dependency_overrides[require_auth] = override_require_auth

def test_get_job_result_not_found(mocker):
    mocker.patch("ytclfr.api.v1.results.get_cached_result", return_value=None)
    mocker.patch("ytclfr.api.v1.results.get_final_output_by_job_id", return_value=None)
    
    job_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/jobs/{job_id}/result")
    assert response.status_code == 404

def test_get_job_result_v1(mocker):
    mocker.patch("ytclfr.api.v1.results.get_cached_result", return_value=None)
    mock_model = mocker.MagicMock()
    mock_model.content_type = "movie_list"
    mock_model.output_json = {"job_id": "123", "content_type": "movie_list"}
    mocker.patch("ytclfr.api.v1.results.get_final_output_by_job_id", return_value=mock_model)
    mocker.patch("ytclfr.api.v1.results.cache_result")
    
    job_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/jobs/{job_id}/result")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "v1"

def test_get_job_result_v2(mocker):
    mocker.patch("ytclfr.api.v1.results.get_cached_result", return_value=None)
    mock_model = mocker.MagicMock()
    mock_model.content_type = "v2_Education"
    
    # Valid V2 data
    v2_data = {
        "job_id": str(uuid.uuid4()),
        "taxonomy": {
            "parent_category": "Education",
            "child_category": "Tutorial",
            "intent": "Learn",
            "confidence": 0.9,
            "groq_taxonomy_used": True
        },
        "summary": "This is a summary",
        "items": [],
        "evidence_graph_summary": [],
        "provenance": {},
        "confidence": {"taxonomy": 0.9},
        "fallback_notes": [],
        "created_at": "2026-05-27T00:00:00Z"
    }
    mock_model.output_json = v2_data
    mocker.patch("ytclfr.api.v1.results.get_final_output_by_job_id", return_value=mock_model)
    mocker.patch("ytclfr.api.v1.results.cache_result")
    
    job_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/jobs/{job_id}/result")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["schema_version"] == "v2"
    assert res_json["pipeline_version"] == "v2.2.0"
    assert res_json["summary"] == "This is a summary"

def test_get_job_segments(mocker):
    mocker.patch("ytclfr.api.v1.results.get_segments_by_time_range", return_value=[])
    job_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/jobs/{job_id}/segments?start_sec=0&end_sec=10")
    assert response.status_code == 200
    assert response.json()["segments"] == []

def test_search_job_segments(mocker):
    mocker.patch("ytclfr.api.v1.results.search_segments_by_keyword", return_value=[])
    job_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/jobs/{job_id}/search?query=test")
    assert response.status_code == 200
    assert response.json()["segments"] == []

def test_get_similar_segments(mocker):
    mocker.patch("ytclfr.api.v1.results.generate_embedding", return_value=[0.1]*768)
    mocker.patch("ytclfr.api.v1.results.search_segments_by_similarity", return_value=[])
    job_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/jobs/{job_id}/similar?query=test")
    assert response.status_code == 200
    assert response.json()["segments"] == []
