from hypothesis import given
from hypothesis import strategies as st

from ytclfr.confidence.controller import ConfidenceVerdict, evaluate


def test_evaluate_all_high_confidence():
    results = [
        {"extractor_type": "asr", "segments": [{"confidence": 0.9}]},
        {"extractor_type": "ocr", "segments": [{"confidence": 0.9}]},
        {
            "extractor_type": "audio",
            "segments": [{"confidence": 0.9, "label": "speech"}],
        },
    ]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    verdict = evaluate(results, timeline, current_attempt=0)
    assert isinstance(verdict, ConfidenceVerdict)
    assert verdict.is_confident is True
    assert verdict.should_proceed is True


def test_evaluate_low_asr_triggers_rescan():
    results = [
        {"extractor_type": "asr", "segments": [{"confidence": 0.3}]},
        {"extractor_type": "ocr", "segments": [{"confidence": 0.9}]},
        {
            "extractor_type": "audio",
            "segments": [{"confidence": 0.9, "label": "speech"}],
        },
    ]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    verdict = evaluate(results, timeline, current_attempt=0)
    assert verdict.should_proceed is False
    assert any(a.action == "rescan_asr" for a in verdict.branch_decision.actions)


def test_evaluate_low_ocr_triggers_rescan():
    results = [
        {"extractor_type": "asr", "segments": [{"confidence": 0.9}]},
        {"extractor_type": "ocr", "segments": [{"confidence": 0.2}]},
        {
            "extractor_type": "audio",
            "segments": [{"confidence": 0.9, "label": "speech"}],
        },
    ]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    verdict = evaluate(results, timeline, current_attempt=0)
    assert verdict.should_proceed is False
    assert any(a.action == "rescan_ocr" for a in verdict.branch_decision.actions)


def test_evaluate_at_max_attempts_downgrades():
    results = [
        {"extractor_type": "asr", "segments": [{"confidence": 0.1}]},
        {"extractor_type": "ocr", "segments": [{"confidence": 0.9}]},
        {
            "extractor_type": "audio",
            "segments": [{"confidence": 0.9, "label": "speech"}],
        },
    ]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    # Max attempts is 2
    verdict = evaluate(results, timeline, current_attempt=2)
    assert any(a.action == "downgrade" for a in verdict.branch_decision.actions)
    assert verdict.should_proceed is True  # Because downgrade is not a rescan


def test_evaluate_empty_extractor_results():
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    verdict = evaluate([], timeline, current_attempt=0)
    assert verdict.is_confident is False
    assert len(verdict.uncertainty_markers) > 0


def test_evaluate_all_errors():
    results = [
        {"extractor_type": "asr", "error": "failed"},
        {"extractor_type": "ocr", "error": "failed"},
        {"extractor_type": "audio", "error": "failed"},
    ]
    timeline = {"total_segments": 0, "has_gaps": False, "segments": []}
    verdict = evaluate(results, timeline, current_attempt=0)
    assert verdict.aggregate_score.overall == 0.0
    assert len(verdict.uncertainty_markers) == 4  # asr, ocr, audio, timeline all low


def test_evaluate_returns_confidence_verdict():
    verdict = evaluate([], {"total_segments": 0}, 0)
    assert isinstance(verdict, ConfidenceVerdict)


def test_evaluate_deterministic():
    results = [
        {"extractor_type": "asr", "segments": [{"confidence": 0.3}]},
        {"extractor_type": "ocr", "segments": [{"confidence": 0.2}]},
        {
            "extractor_type": "audio",
            "segments": [{"confidence": 0.9, "label": "speech"}],
        },
    ]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    v1 = evaluate(results, timeline, 0)
    v2 = evaluate(results, timeline, 0)
    v3 = evaluate(results, timeline, 0)
    assert v1 == v2 == v3


def test_evaluate_uncertain_output_never_silently_dropped():
    results = [{"extractor_type": "asr", "segments": [{"confidence": 0.3}]}]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    verdict = evaluate(results, timeline, 0)
    assert any(
        m.signal_type == "asr" and m.is_uncertain for m in verdict.uncertainty_markers
    )


def test_evaluate_no_db_writes_no_queue_calls():
    # evaluate() should not raise any missing dependency error for db/queue as it's pure
    evaluate([], {"total_segments": 0}, 0)


@given(
    asr_conf=st.floats(0.0, 1.0),
    ocr_conf=st.floats(0.0, 1.0),
    audio_conf=st.floats(0.0, 1.0),
    timeline_conf=st.floats(0.0, 1.0),
)
def test_confidence_score_always_in_range(
    asr_conf, ocr_conf, audio_conf, timeline_conf
):
    results = [
        {"extractor_type": "asr", "segments": [{"confidence": asr_conf}]},
        {"extractor_type": "ocr", "segments": [{"confidence": ocr_conf}]},
        {
            "extractor_type": "audio",
            "segments": [{"confidence": audio_conf, "label": "speech"}],
        },
    ]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": timeline_conf}],
    }
    verdict = evaluate(results, timeline, 0)
    assert 0.0 <= verdict.aggregate_score.overall <= 1.0


# ── Hardened tests from mutation testing audit ──────────────


def test_evaluate_no_audio_cascades_to_uncertainty():
    """Mutation gap: no_audio label should cascade to uncertainty via low audio score."""
    results = [
        {"extractor_type": "asr", "segments": [{"confidence": 0.9}]},
        {"extractor_type": "ocr", "segments": [{"confidence": 0.9}]},
        {
            "extractor_type": "audio",
            "segments": [{"label": "no_audio", "confidence": 0.95}],
        },
    ]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    verdict = evaluate(results, timeline, 0)
    assert verdict.aggregate_score.is_uncertain is True
    assert any(
        m.signal_type == "audio" and m.is_uncertain
        for m in verdict.uncertainty_markers
    )


def test_evaluate_verdict_notes_never_empty():
    """Mutation gap: verdict_notes should always have content."""
    # High confidence case
    results = [
        {"extractor_type": "asr", "segments": [{"confidence": 0.9}]},
        {"extractor_type": "ocr", "segments": [{"confidence": 0.9}]},
        {
            "extractor_type": "audio",
            "segments": [{"confidence": 0.9, "label": "speech"}],
        },
    ]
    timeline = {
        "total_segments": 5,
        "has_gaps": False,
        "segments": [{"confidence": 0.9}],
    }
    v = evaluate(results, timeline, 0)
    assert v.verdict_notes != ""
    assert len(v.verdict_notes) > 0

    # Low confidence case
    v2 = evaluate([], {"total_segments": 0}, 0)
    assert v2.verdict_notes != ""
    assert len(v2.verdict_notes) > 0

