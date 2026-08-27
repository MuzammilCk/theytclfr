from ytclfr.alignment.deduplicator import (
    compute_text_similarity,
    deduplicate_cross_modal,
)
from ytclfr.alignment.normalizer import NormalizedEvidence


def test_similarity_function():
    assert compute_text_similarity("hello", "hello") == 1.0
    assert compute_text_similarity("hello", "HELLO ") == 1.0
    assert compute_text_similarity("abc", "xyz") < 0.1

def test_merge_identical_text_within_window():
    asr = NormalizedEvidence(5.0, 6.0, "asr", "hello world", 0.9, "asr-1")
    ocr = NormalizedEvidence(5.5, None, "ocr", "hello world", 0.8, "ocr-1")
    merged = deduplicate_cross_modal([asr, ocr])

    assert len(merged) == 1
    assert merged[0].source == "merged"
    assert merged[0].text == "hello world"
    assert merged[0].confidence == 0.9

def test_no_merge_outside_window():
    asr = NormalizedEvidence(5.0, 6.0, "asr", "hello world", 0.9, "asr-1")
    ocr = NormalizedEvidence(10.0, None, "ocr", "hello world", 0.8, "ocr-1")
    merged = deduplicate_cross_modal([asr, ocr])

    assert len(merged) == 2

def test_no_merge_below_similarity():
    asr = NormalizedEvidence(5.0, 6.0, "asr", "hello world", 0.9, "asr-1")
    ocr = NormalizedEvidence(5.5, None, "ocr", "goodbye moon", 0.8, "ocr-1")
    merged = deduplicate_cross_modal([asr, ocr])

    assert len(merged) == 2

def test_merged_segment_uses_longer_text():
    asr = NormalizedEvidence(5.0, 6.0, "asr", "hello", 0.9, "asr-1")
    ocr = NormalizedEvidence(5.5, None, "ocr", "hello there", 0.8, "ocr-1")
    merged = deduplicate_cross_modal([asr, ocr])

    assert len(merged) == 1
    assert merged[0].text == "hello there"

def test_merged_segment_ids_combined():
    asr = NormalizedEvidence(5.0, 6.0, "asr", "hello world", 0.9, "asr-1")
    ocr = NormalizedEvidence(5.5, None, "ocr", "hello world", 0.8, "ocr-1")
    merged = deduplicate_cross_modal([asr, ocr])

    assert len(merged) == 1
    assert merged[0].segment_id == "asr-1,ocr-1"
