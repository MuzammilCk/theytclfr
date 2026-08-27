"""Unit tests for Stage B extractor selection logic.

Tests _build_extractor_names — the pure function that determines
which extractors to run based on the SignalManifest. No Celery,
no DB, no mocking of external services required.
"""

import json
from pathlib import Path

import pytest

from ytclfr.contracts.manifest import SignalManifest
from ytclfr.tasks.stage_b import (
    FALLBACK_EXTRACTOR,
    _build_extractor_names,
)


def _make_manifest(**overrides) -> SignalManifest:
    """Build a SignalManifest from the golden fixture with overrides."""
    fixture_path = (
        Path(__file__).parent.parent.parent
        / "fixtures"
        / "signal_manifest_golden.json"
    )
    data = json.loads(fixture_path.read_text())
    data.update(overrides)
    return SignalManifest.model_validate(data)


class TestExtractorSelection:
    """Tests for _build_extractor_names pure function."""

    def test_speech_only_dispatches_asr_and_audio(self):
        """has_speech=True → asr and audio are dispatched."""
        manifest = _make_manifest(
            has_speech=True,
            has_music=False,
            has_burned_in_text=False,
        )
        names = _build_extractor_names(manifest)
        assert "asr" in names
        assert "audio" in names
        assert "ocr" not in names

    def test_speech_and_text_dispatches_asr_ocr_audio(self):
        """has_speech=True + has_burned_in_text=True → all three."""
        manifest = _make_manifest(
            has_speech=True,
            has_music=False,
            has_burned_in_text=True,
        )
        names = _build_extractor_names(manifest)
        assert set(names) == {"asr", "ocr", "audio"}

    def test_music_only_dispatches_audio_only(self):
        """has_music=True + no speech + no text → audio only."""
        manifest = _make_manifest(
            has_speech=False,
            has_music=True,
            has_burned_in_text=False,
        )
        names = _build_extractor_names(manifest)
        assert "audio" in names
        assert "asr" not in names
        assert "ocr" not in names

    def test_burned_in_text_only_dispatches_ocr(self):
        """has_burned_in_text=True + no speech + no music.
        OCR is added. No audio signal → no audio extractor.
        No speech → no ASR. Result: ocr only."""
        manifest = _make_manifest(
            has_speech=False,
            has_music=False,
            has_burned_in_text=True,
        )
        names = _build_extractor_names(manifest)
        assert "ocr" in names
        assert "asr" not in names
        # audio is NOT dispatched (no speech, no music)
        assert "audio" not in names

    def test_no_signals_uses_fallback(self):
        """All signals False → fallback extractor is dispatched."""
        manifest = _make_manifest(
            has_speech=False,
            has_music=False,
            has_burned_in_text=False,
        )
        names = _build_extractor_names(manifest)
        assert len(names) >= 1
        assert FALLBACK_EXTRACTOR in names

    def test_result_always_has_at_least_one_extractor(self):
        """_build_extractor_names always returns at least one item."""
        for speech, music, text in [
            (False, False, False),
            (True, False, False),
            (False, True, False),
            (False, False, True),
            (True, True, True),
        ]:
            manifest = _make_manifest(
                has_speech=speech,
                has_music=music,
                has_burned_in_text=text,
            )
            names = _build_extractor_names(manifest)
            assert len(names) >= 1, (
                f"Empty extractor list for speech={speech} "
                f"music={music} text={text}"
            )

    def test_no_duplicate_extractors(self):
        """_build_extractor_names never returns duplicate names."""
        manifest = _make_manifest(
            has_speech=True,
            has_music=True,
            has_burned_in_text=True,
        )
        names = _build_extractor_names(manifest)
        assert len(names) == len(set(names)), (
            f"Duplicate extractor names: {names}"
        )
