"""Unit tests for SignalManifest Pydantic contract."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from ytclfr.contracts.manifest import SignalManifest

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


def _load_golden_fixture() -> dict:
    """Load the golden JSON fixture for SignalManifest."""
    fixture_path = FIXTURES_DIR / "signal_manifest_golden.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _valid_manifest_dict(**overrides: object) -> dict:
    """Return a valid manifest dict with optional field overrides."""
    data = _load_golden_fixture()
    data.update(overrides)
    return data


class TestSignalManifest:
    """Tests for SignalManifest data contract validation."""

    def test_golden_fixture_validates(self) -> None:
        """Golden JSON fixture must validate into SignalManifest."""
        data = _load_golden_fixture()
        manifest = SignalManifest.model_validate(data)
        assert manifest.job_id == UUID(
            "00000000-0000-0000-0000-000000000099"
        )
        assert manifest.audio_type == "speech_only"
        assert manifest.language == "en"
        assert manifest.has_speech is True
        assert manifest.has_music is False
        assert manifest.has_burned_in_text is True
        assert manifest.has_subtitle_track is False
        assert manifest.has_faces is True
        assert manifest.motion_density == 4.2
        assert manifest.motion_score == 0.31
        assert manifest.aspect_ratio == "16:9"
        assert manifest.content_format == "live_action"
        assert manifest.scene_cut_count == 17
        assert manifest.duration_seconds == 842.0
        assert manifest.probing_confidence == 0.78
        assert manifest.created_at is not None

    def test_probing_confidence_over_one_rejected(self) -> None:
        """probing_confidence > 1.0 must raise ValidationError."""
        data = _valid_manifest_dict(probing_confidence=1.5)
        with pytest.raises(ValidationError):
            SignalManifest.model_validate(data)

    def test_probing_confidence_negative_rejected(self) -> None:
        """probing_confidence < 0.0 must raise ValidationError."""
        data = _valid_manifest_dict(probing_confidence=-0.1)
        with pytest.raises(ValidationError):
            SignalManifest.model_validate(data)

    def test_motion_score_negative_rejected(self) -> None:
        """motion_score < 0.0 must raise ValidationError."""
        data = _valid_manifest_dict(motion_score=-0.1)
        with pytest.raises(ValidationError):
            SignalManifest.model_validate(data)

    def test_motion_score_over_one_rejected(self) -> None:
        """motion_score > 1.0 must raise ValidationError."""
        data = _valid_manifest_dict(motion_score=1.5)
        with pytest.raises(ValidationError):
            SignalManifest.model_validate(data)

    def test_duration_negative_rejected(self) -> None:
        """duration_seconds < 0 must raise ValidationError."""
        data = _valid_manifest_dict(duration_seconds=-1.0)
        with pytest.raises(ValidationError):
            SignalManifest.model_validate(data)

    def test_valid_audio_types_accepted(self) -> None:
        """All valid audio_type literals must be accepted."""
        for audio_type in [
            "speech_only",
            "music_only",
            "speech_music",
            "sfx",
            "ambient",
            "silent",
        ]:
            data = _valid_manifest_dict(audio_type=audio_type)
            manifest = SignalManifest.model_validate(data)
            assert manifest.audio_type == audio_type

    def test_invalid_audio_type_rejected(self) -> None:
        """Invalid audio_type literal must raise ValidationError."""
        data = _valid_manifest_dict(audio_type="invalid_type")
        with pytest.raises(ValidationError):
            SignalManifest.model_validate(data)

    def test_content_format_literals_accepted(self) -> None:
        """All valid content_format literals must be accepted."""
        for fmt in [
            "live_action",
            "animation",
            "screen_recording",
            "mixed",
            "unknown",
        ]:
            data = _valid_manifest_dict(content_format=fmt)
            manifest = SignalManifest.model_validate(data)
            assert manifest.content_format == fmt
