import pytest
from ytclfr.tasks.stage_b import _build_extractor_names
from ytclfr.contracts.manifest import SignalManifest
import uuid

def make_manifest(**kwargs):
    defaults = {
        "job_id": uuid.uuid4(),
        "audio_type": "speech_only",
        "has_speech": False,
        "has_music": False,
        "has_burned_in_text": False,
        "has_subtitle_track": False,
        "has_faces": False,
        "motion_density": 0.0,
        "motion_score": 0.0,
        "aspect_ratio": "16:9",
        "content_format": "unknown",
        "scene_cut_count": 0,
        "duration_seconds": 10.0,
        "probing_confidence": 1.0,
        "structural_score": 0.0,
        "list_likelihood": 0.0,
        "countdown_likelihood": 0.0,
        "overlay_text_density": 0.0,
        "ordinal_pattern_score": 0.0,
        "scene_repeat_score": 0.0,
        "ocr_required": False,
        "ocr_expected_coverage": 0.0,
        "asr_expected_value": 0.5,
        "structural_video_type": "none"
    }
    defaults.update(kwargs)
    return SignalManifest(**defaults)

def test_ocr_dispatched_for_burned_in_text():
    manifest = make_manifest(has_burned_in_text=True, ocr_required=False)
    names = _build_extractor_names(manifest)
    assert "ocr" in names

def test_ocr_dispatched_for_ocr_required():
    manifest = make_manifest(has_burned_in_text=False, ocr_required=True)
    names = _build_extractor_names(manifest)
    assert "ocr" in names

def test_ocr_not_dispatched_if_not_required():
    manifest = make_manifest(has_burned_in_text=False, ocr_required=False, has_speech=True)
    names = _build_extractor_names(manifest)
    assert "ocr" not in names
    assert "asr" in names

def test_asr_dispatched_for_speech():
    manifest = make_manifest(has_speech=True)
    names = _build_extractor_names(manifest)
    assert "asr" in names

def test_audio_dispatched_for_music_or_speech():
    assert "audio" in _build_extractor_names(make_manifest(has_music=True))
    assert "audio" in _build_extractor_names(make_manifest(has_speech=True))

def test_fallback_extractor():
    manifest = make_manifest()
    names = _build_extractor_names(manifest)
    assert len(names) == 1
    assert names[0] == "audio"
