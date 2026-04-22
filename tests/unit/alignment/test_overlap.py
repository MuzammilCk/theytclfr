from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ytclfr.alignment.normalizer import NormalizedEvidence
from ytclfr.alignment.overlap import detect_overlaps, resolve_overlaps


def test_detect_overlaps_finds_overlapping_ranges():
    e1 = NormalizedEvidence(0.0, 2.0, "asr", "a", 0.9, "1")
    e2 = NormalizedEvidence(1.0, 3.0, "asr", "b", 0.9, "2")
    overlaps = detect_overlaps([e1, e2])
    assert len(overlaps) == 1
    assert overlaps[0] == (e1, e2)

def test_detect_overlaps_point_in_range():
    e1 = NormalizedEvidence(0.0, 2.0, "asr", "a", 0.9, "1")
    e2 = NormalizedEvidence(1.0, None, "ocr", "b", 0.9, "2")
    overlaps = detect_overlaps([e1, e2])
    assert len(overlaps) == 1

def test_detect_overlaps_no_overlap():
    e1 = NormalizedEvidence(0.0, 1.0, "asr", "a", 0.9, "1")
    e2 = NormalizedEvidence(2.0, 3.0, "asr", "b", 0.9, "2")
    overlaps = detect_overlaps([e1, e2])
    assert len(overlaps) == 0

def test_resolve_overlaps_keeps_higher_confidence():
    e1 = NormalizedEvidence(0.0, 2.0, "asr", "a", 0.8, "1")
    e2 = NormalizedEvidence(1.0, 3.0, "asr", "b", 0.9, "2")
    resolved = resolve_overlaps([e1, e2])
    assert len(resolved) == 1
    assert resolved[0] == e2

def test_resolve_overlaps_keeps_cross_source():
    e1 = NormalizedEvidence(0.0, 2.0, "asr", "a", 0.8, "1")
    e2 = NormalizedEvidence(1.0, None, "ocr", "b", 0.9, "2")
    resolved = resolve_overlaps([e1, e2])
    assert len(resolved) == 2

def test_resolve_overlaps_deterministic_on_tie():
    e1 = NormalizedEvidence(0.0, 2.0, "asr", "a", 0.9, "1")
    e2 = NormalizedEvidence(1.0, 3.0, "asr", "b", 0.9, "2")
    resolved = resolve_overlaps([e1, e2])
    assert len(resolved) == 1
    assert resolved[0] == e1

@st.composite
def evidence_strategy(draw):
    start = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False))
    is_point = draw(st.booleans())
    if is_point:
        end = None
    else:
        end = draw(
            st.floats(
                min_value=start, max_value=start + 100.0, allow_nan=False
            )
        )
    return NormalizedEvidence(
        start_sec=start,
        end_sec=end,
        source=draw(st.sampled_from(["asr", "ocr"])),
        text=draw(st.text(min_size=1, max_size=10)),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        segment_id=draw(st.text(min_size=1, max_size=5))
    )

@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=10)
@given(st.lists(evidence_strategy(), max_size=20))
def test_overlap_resolution_never_increases_count(evidence):
    resolved = resolve_overlaps(evidence)
    assert len(resolved) <= len(evidence)

@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=10)
@given(st.lists(evidence_strategy(), max_size=20))
def test_overlap_resolution_preserves_all_text(evidence):
    resolved = resolve_overlaps(evidence)
    for r in resolved:
        assert any(r.text == e.text for e in evidence)

@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=10)
@given(st.lists(evidence_strategy(), max_size=20))
def test_overlap_resolution_maintains_sort_order(evidence):
    resolved = resolve_overlaps(evidence)
    for i in range(len(resolved) - 1):
        assert resolved[i].start_sec <= resolved[i + 1].start_sec
