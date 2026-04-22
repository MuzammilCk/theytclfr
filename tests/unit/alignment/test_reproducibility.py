import uuid

from ytclfr.alignment.engine import align


def _assert_timelines_identical(t1, t2):
    assert t1.job_id == t2.job_id
    assert t1.total_segments == t2.total_segments
    assert t1.has_gaps == t2.has_gaps
    for s1, s2 in zip(t1.segments, t2.segments):
        assert s1.timestamp == s2.timestamp
        assert s1.end_timestamp == s2.end_timestamp
        assert s1.source == s2.source
        assert s1.text == s2.text
        assert s1.confidence == s2.confidence
        assert s1.original_segment_ids == s2.original_segment_ids

def test_reproducibility_three_runs():
    job_id = uuid.uuid4()
    results = [
        {
            "extractor_type": "asr",
            "error": None,
            "segments": [
                {
                    "start_time": 0.0, "end_time": 1.0,
                    "text": "hello", "confidence": 0.9
                },
                {
                    "start_time": 2.0, "end_time": 3.0,
                    "text": "world", "confidence": 0.8
                },
            ]
        }
    ]

    t1 = align(job_id, results)
    t2 = align(job_id, results)
    t3 = align(job_id, results)

    _assert_timelines_identical(t1, t2)
    _assert_timelines_identical(t2, t3)

def test_reproducibility_with_overlaps():
    job_id = uuid.uuid4()
    results = [
        {
            "extractor_type": "asr",
            "error": None,
            "segments": [
                {
                    "start_time": 0.0, "end_time": 2.0,
                    "text": "hello", "confidence": 0.9
                },
                {
                    "start_time": 1.0, "end_time": 3.0,
                    "text": "hello", "confidence": 0.8
                },
            ]
        }
    ]

    t1 = align(job_id, results)
    t2 = align(job_id, results)
    t3 = align(job_id, results)

    _assert_timelines_identical(t1, t2)
    _assert_timelines_identical(t2, t3)

def test_reproducibility_with_merges():
    job_id = uuid.uuid4()
    results = [
        {
            "extractor_type": "asr",
            "error": None,
            "segments": [
                {
                    "start_time": 0.0, "end_time": 2.0,
                    "text": "hello world", "confidence": 0.9
                },
            ]
        },
        {
            "extractor_type": "ocr",
            "error": None,
            "segments": [
                {
                    "frame_timestamp": 0.5, "text": "hello world",
                    "confidence": 0.8
                },
            ]
        }
    ]

    t1 = align(job_id, results)
    t2 = align(job_id, results)
    t3 = align(job_id, results)

    _assert_timelines_identical(t1, t2)
    _assert_timelines_identical(t2, t3)
