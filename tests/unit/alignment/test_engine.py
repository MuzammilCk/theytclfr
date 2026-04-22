import uuid

from ytclfr.alignment.engine import align
from ytclfr.contracts.alignment import AlignedTimeline


def test_align_empty_input():
    job_id = uuid.uuid4()
    timeline = align(job_id, [])
    assert timeline.total_segments == 0
    assert len(timeline.segments) == 0
    assert timeline.has_gaps is False
    assert timeline.job_id == job_id

def test_align_all_errors():
    job_id = uuid.uuid4()
    results = [
        {"extractor_type": "asr", "error": "failed"},
        {"extractor_type": "ocr", "error": "failed"}
    ]
    timeline = align(job_id, results)
    assert timeline.total_segments == 0

def test_align_asr_only():
    job_id = uuid.uuid4()
    results = [
        {
            "extractor_type": "asr",
            "error": None,
            "segments": [
                {"start_time": 0.0, "end_time": 1.0, "text": "hello", "confidence": 0.9}
            ]
        }
    ]
    timeline = align(job_id, results)
    assert timeline.total_segments == 1
    assert timeline.segments[0].source == "asr"

def test_align_ocr_only():
    job_id = uuid.uuid4()
    results = [
        {
            "extractor_type": "ocr",
            "error": None,
            "segments": [
                {"frame_timestamp": 0.5, "text": "A", "confidence": 0.8}
            ]
        }
    ]
    timeline = align(job_id, results)
    assert timeline.total_segments == 1
    assert timeline.segments[0].source == "ocr"

def test_align_full_pipeline():
    job_id = uuid.uuid4()
    results = [
        {
            "extractor_type": "asr",
            "error": None,
            "segments": [
                {
                    "start_time": 0.0, "end_time": 2.0, "text": "hello world",
                    "confidence": 0.9
                },
                {
                    "start_time": 1.0, "end_time": 3.0, "text": "hello world",
                    "confidence": 0.8
                },
            ]
        },
        {
            "extractor_type": "ocr",
            "error": None,
            "segments": [
                {
                    "frame_timestamp": 0.5, "text": "hello world",
                    "confidence": 0.85
                },
                {
                    "frame_timestamp": 10.0, "text": "something else",
                    "confidence": 0.9
                }
            ]
        }
    ]
    timeline = align(job_id, results)
    assert timeline.total_segments == 2
    assert timeline.segments[0].source == "merged"
    assert timeline.segments[1].source == "ocr"
    assert timeline.has_gaps is True

def test_align_conforms_to_schema():
    job_id = uuid.uuid4()
    results = [
        {
            "extractor_type": "asr",
            "error": None,
            "segments": [
                {"start_time": 0.0, "end_time": 1.0, "text": "hello", "confidence": 0.9}
            ]
        }
    ]
    timeline = align(job_id, results)
    # This will raise ValidationError if it doesn't conform
    AlignedTimeline.model_validate(timeline.model_dump())
