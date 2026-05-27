import pytest
from ytclfr.probing.ocr_pattern_scorer import score_ocr_patterns

def test_score_ocr_patterns_empty():
    res = score_ocr_patterns([])
    assert res.ordinal_pattern_score == 0.0
    assert res.countdown_likelihood == 0.0

def test_score_ocr_patterns_high_density_no_countdown():
    # Sequence of numbers but not going down consistently
    segments = [
        {"text": "Top 10 movies", "timestamp": 1.0},
        {"text": "Number 2 is great", "timestamp": 2.0},
        {"text": "100 percent real", "timestamp": 3.0},
        {"text": "Rank 5", "timestamp": 4.0},
        {"text": "Just words", "timestamp": 5.0}
    ]
    res = score_ocr_patterns(segments)
    # 4 out of 5 segments have numbers: density = 0.8
    # ordinal_score = 0.8 * 5 = 4.0, capped at 1.0
    assert res.ordinal_pattern_score == 1.0
    # decreasing: 10->2 (yes), 2->100 (no), 100->5 (yes)
    # decrements = 2, increments = 1
    # decrements > increments, so score = (2 / 3) * 1.5 = 1.0
    assert res.countdown_likelihood == 1.0

def test_score_ocr_patterns_countdown():
    segments = [
        {"text": "10", "timestamp": 1.0},
        {"text": "9", "timestamp": 2.0},
        {"text": "8", "timestamp": 3.0},
        {"text": "7", "timestamp": 4.0}
    ]
    res = score_ocr_patterns(segments)
    assert res.ordinal_pattern_score == 1.0
    assert res.countdown_likelihood == 1.0

def test_score_ocr_patterns_no_numbers():
    segments = [
        {"text": "hello", "timestamp": 1.0},
        {"text": "world", "timestamp": 2.0}
    ]
    res = score_ocr_patterns(segments)
    assert res.ordinal_pattern_score == 0.0
    assert res.countdown_likelihood == 0.0
