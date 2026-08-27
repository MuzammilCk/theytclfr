from hypothesis import given
from hypothesis import strategies as st

from ytclfr.confidence.scorer import (
    SignalScore,
    compute_aggregate_score,
    score_asr,
    score_audio,
    score_ocr,
    score_timeline,
)


def test_score_asr_high_confidence():
    results = [
        {
            "extractor_type": "asr",
            "segments": [{"confidence": 0.9}, {"confidence": 0.9}],
        }
    ]
    score = score_asr(results)
    assert score.level == "high"
    assert score.score == 0.9
    assert score.has_data is True
    assert score.segment_count == 2


def test_score_asr_low_confidence():
    results = [
        {
            "extractor_type": "asr",
            "segments": [{"confidence": 0.3}, {"confidence": 0.3}],
        }
    ]
    score = score_asr(results)
    assert score.level == "low"
    assert score.score == 0.3
    assert score.has_data is True


def test_score_asr_missing_result():
    score = score_asr([])
    assert score.score == 0.0
    assert score.has_data is False
    assert score.level == "low"


def test_score_asr_error_result():
    results = [{"extractor_type": "asr", "error": "failed"}]
    score = score_asr(results)
    assert score.score == 0.0
    assert score.has_data is False


def test_score_ocr_high_confidence():
    results = [
        {
            "extractor_type": "ocr",
            "segments": [{"confidence": 0.8}, {"confidence": 0.8}],
        }
    ]
    score = score_ocr(results)
    assert score.level == "high"
    assert score.score == 0.8


def test_score_ocr_no_segments():
    results = [{"extractor_type": "ocr", "segments": []}]
    score = score_ocr(results)
    assert score.score == 0.0
    assert score.level == "low"
    assert score.has_data is False


def test_score_audio_speech_label():
    results = [
        {
            "extractor_type": "audio",
            "segments": [{"label": "speech", "confidence": 0.7}],
        }
    ]
    score = score_audio(results)
    assert score.score == 0.7
    assert score.level == "medium"


def test_score_audio_no_audio_label():
    results = [
        {
            "extractor_type": "audio",
            "segments": [{"label": "no_audio", "confidence": 0.9}],
        }
    ]
    score = score_audio(results)
    assert score.score == 0.0
    assert score.level == "low"
    assert score.has_data is True


def test_score_timeline_empty():
    timeline_dict = {"total_segments": 0, "has_gaps": False, "segments": []}
    score = score_timeline(timeline_dict)
    assert score.score == 0.0
    assert score.level == "low"


def test_score_timeline_with_gaps():
    timeline_dict = {
        "total_segments": 5,
        "has_gaps": True,
        "segments": [{"confidence": 0.8}],
    }
    score = score_timeline(timeline_dict)
    assert score.score == 0.65  # 0.8 - 0.15


def test_aggregate_score_weighted_average():
    asr = SignalScore("asr", 1.0, "high", 1, True, "")
    ocr = SignalScore("ocr", 1.0, "high", 1, True, "")
    audio = SignalScore("audio", 1.0, "high", 1, True, "")
    timeline = SignalScore("timeline", 1.0, "high", 1, True, "")
    agg = compute_aggregate_score(asr, ocr, audio, timeline)
    assert agg.overall == 1.0
    assert agg.is_uncertain is False


def test_aggregate_is_uncertain_when_any_low():
    asr = SignalScore("asr", 1.0, "high", 1, True, "")
    ocr = SignalScore("ocr", 0.1, "low", 1, True, "")
    audio = SignalScore("audio", 1.0, "high", 1, True, "")
    timeline = SignalScore("timeline", 1.0, "high", 1, True, "")
    agg = compute_aggregate_score(asr, ocr, audio, timeline)
    assert agg.is_uncertain is True


@given(
    asr_score=st.floats(0.0, 1.0),
    ocr_score=st.floats(0.0, 1.0),
    audio_score=st.floats(0.0, 1.0),
    timeline_score=st.floats(0.0, 1.0),
)
def test_all_scores_clamped_to_valid_range(
    asr_score, ocr_score, audio_score, timeline_score
):
    asr = SignalScore("asr", asr_score, "high", 1, True, "")
    ocr = SignalScore("ocr", ocr_score, "high", 1, True, "")
    audio = SignalScore("audio", audio_score, "high", 1, True, "")
    timeline = SignalScore("timeline", timeline_score, "high", 1, True, "")
    agg = compute_aggregate_score(asr, ocr, audio, timeline)
    assert 0.0 <= agg.overall <= 1.0


# ── Hardened tests from mutation testing audit ──────────────


def test_score_asr_medium_at_boundary():
    """Mutation gap: no test for score exactly at ASR_LOW_CONFIDENCE boundary."""
    results = [
        {
            "extractor_type": "asr",
            "segments": [{"confidence": 0.40}],
        }
    ]
    score = score_asr(results)
    assert score.level == "medium"
    assert score.score == 0.40


def test_score_ocr_medium_level():
    """Mutation gap: no test for OCR medium classification."""
    results = [
        {
            "extractor_type": "ocr",
            "segments": [{"confidence": 0.50}],
        }
    ]
    score = score_ocr(results)
    assert score.level == "medium"


def test_score_asr_returns_correct_signal_type():
    """Mutation gap: no test checks signal_type field value."""
    results = [
        {
            "extractor_type": "asr",
            "segments": [{"confidence": 0.9}],
        }
    ]
    score = score_asr(results)
    assert score.signal_type == "asr"


def test_score_ocr_returns_correct_signal_type():
    """Mutation gap: signal_type could be wrong if copy-pasted."""
    results = [
        {
            "extractor_type": "ocr",
            "segments": [{"confidence": 0.9}],
        }
    ]
    score = score_ocr(results)
    assert score.signal_type == "ocr"


def test_score_audio_returns_correct_signal_type():
    """Mutation gap: signal_type could be wrong if copy-pasted."""
    results = [
        {
            "extractor_type": "audio",
            "segments": [{"confidence": 0.9, "label": "speech"}],
        }
    ]
    score = score_audio(results)
    assert score.signal_type == "audio"


def test_aggregate_weights_sum_to_one():
    """Mutation gap: if weights don't sum to 1.0, overall score is wrong."""
    from ytclfr.confidence.scorer import (
        ASR_WEIGHT,
        AUDIO_WEIGHT,
        OCR_WEIGHT,
        TIMELINE_WEIGHT,
    )

    total = ASR_WEIGHT + OCR_WEIGHT + AUDIO_WEIGHT + TIMELINE_WEIGHT
    assert total == 1.0, f"Weights sum to {total}, not 1.0"


def test_score_timeline_boundary_at_min_segments():
    """Mutation gap: no test for total_segments exactly at TIMELINE_MIN_SEGMENTS."""
    from ytclfr.confidence.scorer import TIMELINE_MIN_SEGMENTS

    timeline_dict = {
        "total_segments": TIMELINE_MIN_SEGMENTS,
        "has_gaps": False,
        "segments": [{"confidence": 0.8}],
    }
    score = score_timeline(timeline_dict)
    # Should pass the min_segments check and compute avg score
    assert score.score == 0.8
    assert score.level == "high"

