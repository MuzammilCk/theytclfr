"""Tests for the classifier module."""

from uuid import uuid4

from ytclfr.contracts.router import RouterDecision
from ytclfr.router.audio_checker import AudioCheckResult
from ytclfr.router.classifier import (
    HIGH_CONFIDENCE,
    MIXED_CONFIDENCE,
    classify,
)
from ytclfr.router.metadata_inspector import MetadataSignals


def _make_audio(
    has_audio: bool = False,
    likely_music: bool = False,
    codec: str | None = None,
    bitrate: float | None = None,
) -> AudioCheckResult:
    return AudioCheckResult(
        has_audio=has_audio,
        audio_codec=codec,
        audio_bitrate_kbps=bitrate,
        likely_music=likely_music,
    )


def _make_meta(
    title: str = "",
    has_list: bool = False,
    has_recipe: bool = False,
    has_slide: bool = False,
    matched: list[str] | None = None,
) -> MetadataSignals:
    return MetadataSignals(
        title=title,
        has_list_signal=has_list,
        has_recipe_signal=has_recipe,
        has_slide_signal=has_slide,
        has_description=False,
        tag_count=0,
        matched_keywords=matched or [],
    )


def test_classifies_music_heavy():
    """Test music-heavy classification when likely_music is True."""
    audio = _make_audio(has_audio=True, likely_music=True, bitrate=192.0)
    meta = _make_meta()
    decision = classify(uuid4(), audio, meta, 5, 240.0)
    assert decision.primary_route == "music-heavy"
    assert decision.confidence >= 0.8


def test_classifies_list_edit():
    """Test list-edit classification with list keywords."""
    audio = _make_audio()
    meta = _make_meta(
        has_list=True,
        matched=["top", "best"],
    )
    decision = classify(uuid4(), audio, meta, 5, 600.0)
    assert decision.primary_route == "list-edit"
    assert decision.confidence == HIGH_CONFIDENCE


def test_classifies_speech_heavy_on_recipe():
    """Test speech-heavy classification with recipe signal."""
    audio = _make_audio(has_audio=True)
    meta = _make_meta(has_recipe=True, matched=["recipe"])
    decision = classify(uuid4(), audio, meta, 5, 300.0)
    assert decision.primary_route == "speech-heavy"


def test_falls_back_to_mixed():
    """Test fallback to mixed when no strong signals."""
    audio = _make_audio()
    meta = _make_meta()
    decision = classify(uuid4(), audio, meta, 5, 300.0)
    assert decision.primary_route == "mixed"
    assert decision.confidence == MIXED_CONFIDENCE


def test_confidence_in_valid_range():
    """Test that confidence is always in [0, 1] for all route types."""
    scenarios = [
        # music-heavy
        (_make_audio(has_audio=True, likely_music=True), _make_meta()),
        # slide-presentation
        (_make_audio(), _make_meta(has_slide=True)),
        # list-edit
        (_make_audio(), _make_meta(has_list=True, matched=["top"])),
        # speech-heavy
        (_make_audio(has_audio=True), _make_meta(has_recipe=True)),
        # mixed
        (_make_audio(), _make_meta()),
    ]
    for audio, meta in scenarios:
        decision = classify(uuid4(), audio, meta, 5, 300.0)
        assert 0.0 <= decision.confidence <= 1.0, (
            f"Confidence {decision.confidence} out of range "
            f"for route {decision.primary_route}"
        )


def test_decision_conforms_to_contract():
    """Test that classify returns a valid RouterDecision from Phase 1 contract."""
    audio = _make_audio(has_audio=True, likely_music=True)
    meta = _make_meta()
    decision = classify(uuid4(), audio, meta, 5, 240.0)
    assert isinstance(decision, RouterDecision)
    assert decision.primary_route in (
        "speech-heavy",
        "music-heavy",
        "list-edit",
        "slide-presentation",
        "mixed",
    )


def test_music_routes_correctly_despite_list_keyword():
    """Music with superlatives in the title must still route
    as music-heavy. Regression for Rule 1 guard bug.
    audio.likely_music=True takes priority over list keywords.
    """
    audio = _make_audio(has_audio=True, likely_music=True, bitrate=192.0)
    meta = _make_meta(
        title="Best of Taylor Swift Compilation",
        has_list=True,
        matched=["best of"],
    )
    decision = classify(uuid4(), audio, meta, 5, 240.0)
    assert decision.primary_route == "music-heavy"
    assert decision.confidence == HIGH_CONFIDENCE


def test_ringtone_routes_as_music_heavy():
    """20-second ringtone with high bitrate must route as
    music-heavy. This is the end-to-end regression test
    for the original reported bug.
    """
    audio = _make_audio(has_audio=True, likely_music=True, bitrate=192.0)
    meta = _make_meta(title="Best iPhone Ringtone 2024")
    decision = classify(uuid4(), audio, meta, 5, 20.0)
    assert decision.primary_route == "music-heavy"


def test_music_blocked_below_minimum_duration():
    """A 5-second stub/test file must not route as music
    even with high bitrate audio.
    """
    audio = _make_audio(has_audio=True, likely_music=True, bitrate=192.0)
    meta = _make_meta()
    decision = classify(uuid4(), audio, meta, 0, 5.0)
    # Below MUSIC_MIN_DURATION_SECONDS — should not be music
    assert decision.primary_route != "music-heavy"


def test_routing_notes_include_duration_for_music():
    """Router notes for music-heavy must include duration
    so operators can debug misclassifications in logs.
    """
    audio = _make_audio(has_audio=True, likely_music=True, bitrate=192.0)
    meta = _make_meta()
    decision = classify(uuid4(), audio, meta, 5, 180.0)
    assert decision.primary_route == "music-heavy"
    assert "180.0" in (decision.routing_notes or "")
