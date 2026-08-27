from ytclfr.alignment.normalizer import NormalizedEvidence
from ytclfr.alignment.segmenter import create_segments, detect_gaps
from ytclfr.contracts.alignment import AlignedSegment


def test_create_segments_maps_fields_correctly():
    e1 = NormalizedEvidence(0.0, 1.0, "asr", "text", 0.9, "asr-1")
    segments = create_segments([e1])

    assert len(segments) == 1
    s = segments[0]
    assert s.timestamp == 0.0
    assert s.end_timestamp == 1.0
    assert s.source == "asr"
    assert s.text == "text"
    assert s.confidence == 0.9
    assert s.original_segment_ids == ["asr-1"]

def test_create_segments_sorts_by_timestamp():
    e1 = NormalizedEvidence(2.0, 3.0, "asr", "a", 0.9, "1")
    e2 = NormalizedEvidence(0.0, 1.0, "ocr", "b", 0.9, "2")
    segments = create_segments([e1, e2])

    assert len(segments) == 2
    assert segments[0].timestamp == 0.0
    assert segments[1].timestamp == 2.0

def test_detect_gaps_true_when_gap_exists():
    segments = [
        AlignedSegment(
            timestamp=0.0, end_timestamp=1.0, source="asr", text="a",
            confidence=0.9, original_segment_ids=["1"]
        ),
        AlignedSegment(
            timestamp=6.0, end_timestamp=7.0, source="asr", text="b",
            confidence=0.9, original_segment_ids=["2"]
        ),
    ]
    assert detect_gaps(segments) is True

def test_detect_gaps_false_when_continuous():
    segments = [
        AlignedSegment(
            timestamp=0.0, end_timestamp=1.0, source="asr", text="a",
            confidence=0.9, original_segment_ids=["1"]
        ),
        AlignedSegment(
            timestamp=1.5, end_timestamp=2.5, source="asr", text="b",
            confidence=0.9, original_segment_ids=["2"]
        ),
    ]
    assert detect_gaps(segments) is False

def test_detect_gaps_empty_list():
    assert detect_gaps([]) is False

def test_segment_ids_split_correctly():
    e1 = NormalizedEvidence(0.0, 1.0, "merged", "text", 0.9, "asr-1,ocr-1")
    segments = create_segments([e1])
    assert segments[0].original_segment_ids == ["asr-1", "ocr-1"]
