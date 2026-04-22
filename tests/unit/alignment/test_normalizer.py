from ytclfr.alignment.normalizer import normalize_extractor_results


def test_normalize_asr_segments():
    results = [{
        "extractor_type": "asr",
        "error": None,
        "segments": [
            {"start_time": 0.0, "end_time": 1.0, "text": "hello", "confidence": 0.9},
            {"start_time": 1.0, "end_time": 2.0, "text": "world", "confidence": 0.8},
            {"start_time": 2.0, "end_time": 3.0, "text": "!", "confidence": 0.99},
        ]
    }]

    evidence = normalize_extractor_results(results)

    assert len(evidence) == 3
    assert evidence[0].start_sec == 0.0
    assert evidence[0].end_sec == 1.0
    assert evidence[0].source == "asr"
    assert evidence[0].text == "hello"
    assert evidence[0].confidence == 0.9
    assert evidence[0].segment_id == "asr-0"

def test_normalize_ocr_segments():
    results = [{
        "extractor_type": "ocr",
        "error": None,
        "segments": [
            {"frame_timestamp": 0.5, "text": "A", "confidence": 0.7},
            {"frame_timestamp": 1.5, "text": "B", "confidence": 0.8},
            {"frame_timestamp": 2.5, "text": "C", "confidence": 0.9},
        ]
    }]

    evidence = normalize_extractor_results(results)

    assert len(evidence) == 3
    assert evidence[0].start_sec == 0.5
    assert evidence[0].end_sec is None
    assert evidence[0].source == "ocr"
    assert evidence[0].text == "A"
    assert evidence[0].confidence == 0.7
    assert evidence[0].segment_id == "ocr-0"

def test_normalize_skips_audio_segments():
    results = [{
        "extractor_type": "audio",
        "error": None,
        "segments": [{"label": "speech", "confidence": 0.9}]
    }]

    evidence = normalize_extractor_results(results)
    assert len(evidence) == 0

def test_normalize_skips_error_results():
    results = [{
        "extractor_type": "asr",
        "error": "Some error occurred",
        "segments": [
            {"start_time": 0.0, "end_time": 1.0, "text": "hello", "confidence": 0.9}
        ]
    }]

    evidence = normalize_extractor_results(results)
    assert len(evidence) == 0

def test_normalize_sorts_by_start_sec():
    results = [
        {
            "extractor_type": "asr",
            "error": None,
            "segments": [
                {"start_time": 2.0, "end_time": 3.0, "text": "two", "confidence": 0.9}
            ]
        },
        {
            "extractor_type": "ocr",
            "error": None,
            "segments": [
                {"frame_timestamp": 1.0, "text": "first", "confidence": 0.9}
            ]
        }
    ]

    evidence = normalize_extractor_results(results)
    assert len(evidence) == 2
    assert evidence[0].start_sec == 1.0
    assert evidence[0].source == "ocr"
    assert evidence[1].start_sec == 2.0
    assert evidence[1].source == "asr"

def test_normalize_empty_input():
    evidence = normalize_extractor_results([])
    assert len(evidence) == 0
