from hypothesis import given
from hypothesis import strategies as st

from ytclfr.confidence.policy import build_rescan_policy, mark_uncertain_outputs
from ytclfr.confidence.scorer import SignalScore


def test_can_rescan_when_under_max():
    policy = build_rescan_policy(0)
    assert policy.can_rescan is True


def test_cannot_rescan_at_max():
    # max_attempts is 2 by default
    policy = build_rescan_policy(2)
    assert policy.can_rescan is False


def test_ocr_extra_frames_increase_per_attempt():
    policy0 = build_rescan_policy(0)
    policy1 = build_rescan_policy(1)
    assert policy0.ocr_extra_frames == 3
    assert policy1.ocr_extra_frames == 6


def test_mark_uncertain_low_signal():
    signal = SignalScore("asr", 0.3, "low", 1, True, "notes")
    markers = mark_uncertain_outputs([signal])
    assert len(markers) == 1
    assert markers[0].is_uncertain is True


def test_mark_uncertain_high_signal():
    signal = SignalScore("asr", 0.9, "high", 1, True, "notes")
    markers = mark_uncertain_outputs([signal])
    assert len(markers) == 0


def test_uncertain_is_valid_not_error():
    signal = SignalScore("asr", 0.3, "low", 1, True, "notes")
    markers = mark_uncertain_outputs([signal])
    assert not hasattr(markers[0], "error")
    assert hasattr(markers[0], "is_uncertain")


@given(attempt=st.integers(min_value=2, max_value=100))
def test_max_rescan_prevents_infinite_loop(attempt):
    policy = build_rescan_policy(attempt)
    assert policy.can_rescan is False


# ── Hardened tests from mutation testing audit ──────────────


def test_mark_uncertain_medium_signal_not_marked():
    """Mutation gap: medium level should NOT produce uncertainty marker."""
    signal = SignalScore("asr", 0.5, "medium", 1, True, "notes")
    markers = mark_uncertain_outputs([signal])
    assert len(markers) == 0


def test_mark_uncertain_mixed_levels():
    """Verify only low signals get markers when mixed with high and medium."""
    signals = [
        SignalScore("asr", 0.9, "high", 1, True, ""),
        SignalScore("ocr", 0.5, "medium", 1, True, ""),
        SignalScore("audio", 0.1, "low", 1, True, "low audio"),
        SignalScore("timeline", 0.8, "high", 1, True, ""),
    ]
    markers = mark_uncertain_outputs(signals)
    assert len(markers) == 1
    assert markers[0].signal_type == "audio"
    assert markers[0].is_uncertain is True

