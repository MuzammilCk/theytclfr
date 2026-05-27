import pytest
from uuid import uuid4
from ytclfr.fusion.conflict_resolver import resolve_conflicts
from ytclfr.contracts.evidence import FusedSegment
from ytclfr.contracts.manifest import SignalManifest


def _make_manifest(**overrides) -> SignalManifest:
    """Build a minimal valid SignalManifest with sensible defaults."""
    defaults = dict(
        job_id=uuid4(),
        audio_type="speech_only",
        language="en",
        has_speech=True,
        has_music=False,
        has_burned_in_text=False,
        has_subtitle_track=False,
        has_faces=False,
        motion_density=2.0,
        motion_score=0.3,
        aspect_ratio="16:9",
        content_format="live_action",
        scene_cut_count=5,
        duration_seconds=120.0,
        probing_confidence=0.8,
    )
    defaults.update(overrides)
    return SignalManifest(**defaults)


def test_resolve_conflicts_structured_favors_ocr():
    manifest = _make_manifest(has_speech=True)
    asr_segments = [FusedSegment(text="Hello", timestamp=0.0, end_timestamp=1.0, source="asr", confidence=0.8)]
    ocr_segments = [FusedSegment(text="Top 10 list", timestamp=0.0, end_timestamp=1.0, source="ocr", confidence=0.9)]

    result = resolve_conflicts(asr_segments, ocr_segments, "list", manifest)

    assert result.primary_evidence_modality == "ocr"
    assert any("OCR prioritized" in n for n in result.evidence_priority_notes)


def test_resolve_conflicts_speech_heavy_favors_asr():
    manifest = _make_manifest(has_speech=True)
    asr_segments = [FusedSegment(text="Today we talk about science", timestamp=0.0, end_timestamp=2.0, source="asr", confidence=0.95)]
    ocr_segments = [FusedSegment(text="Science", timestamp=0.0, end_timestamp=2.0, source="ocr", confidence=0.6)]

    result = resolve_conflicts(asr_segments, ocr_segments, "none", manifest)

    assert result.primary_evidence_modality == "asr"
    assert any("ASR prioritized" in n for n in result.evidence_priority_notes)


def test_resolve_conflicts_structural_no_ocr_falls_back():
    manifest = _make_manifest(has_speech=True)
    asr_segments = [FusedSegment(text="Number one", timestamp=0.0, end_timestamp=1.0, source="asr", confidence=0.7)]
    ocr_segments = []

    result = resolve_conflicts(asr_segments, ocr_segments, "ranking", manifest)

    assert result.primary_evidence_modality == "mixed"
    assert any("OCR is missing" in n for n in result.evidence_priority_notes)


def test_resolve_conflicts_no_speech_ocr_only():
    manifest = _make_manifest(has_speech=False)
    asr_segments = []
    ocr_segments = [FusedSegment(text="Step 1", timestamp=0.0, end_timestamp=1.0, source="ocr", confidence=0.85)]

    result = resolve_conflicts(asr_segments, ocr_segments, "none", manifest)

    assert result.primary_evidence_modality == "ocr"
    assert any("OCR prioritized" in n for n in result.evidence_priority_notes)


def test_resolve_conflicts_structural_counts_conflict():
    manifest = _make_manifest(has_speech=True)
    asr_segments = [FusedSegment(text="Great song", timestamp=0.0, end_timestamp=1.0, source="asr", confidence=0.9)]
    ocr_segments = [FusedSegment(text="#1 Best Product", timestamp=0.0, end_timestamp=1.0, source="ocr", confidence=0.85)]

    result = resolve_conflicts(asr_segments, ocr_segments, "list", manifest)

    assert result.conflict_count >= 1
    assert any(d["resolution"] == "ocr_wins" for d in result.conflict_details)


def test_resolve_conflicts_applies_asr_discount():
    manifest = _make_manifest(has_speech=True, asr_expected_value=0.2)
    asr_segments = [FusedSegment(text="Oh baby", timestamp=0.0, end_timestamp=1.0, source="asr", confidence=0.9)]
    ocr_segments = []

    result = resolve_conflicts(asr_segments, ocr_segments, "none", manifest)
    
    # Confidence should be scaled by 0.2
    assert result.adjusted_asr_segments is not None
    assert result.adjusted_asr_segments[0].confidence == pytest.approx(0.18)
    assert any("Discounting ASR segment confidences" in n for n in result.evidence_priority_notes)
