from uuid import uuid4

from ytclfr.contracts.extractor import ExtractorResult
from ytclfr.extractors.audio_classifier import classify_audio_from_metadata


def test_speech_label_for_audio_without_music_heuristic():
    metadata_raw = {"acodec": "aac", "abr": 64.0, "duration": 300.0}
    result = classify_audio_from_metadata(uuid4(), metadata_raw)
    assert result.segments[0].text == "speech"


def test_music_label_for_high_bitrate_audio():
    metadata_raw = {"acodec": "aac", "abr": 192.0, "subtitles": {}, "duration": 240.0}
    result = classify_audio_from_metadata(uuid4(), metadata_raw)
    assert result.segments[0].text == "music"


def test_no_audio_label_when_acodec_is_none():
    metadata_raw = {"acodec": "none", "duration": 120.0}
    result = classify_audio_from_metadata(uuid4(), metadata_raw)
    assert result.segments[0].text == "no_audio"


def test_result_conforms_to_extractor_result_schema():
    metadata_raw = {"acodec": "aac", "abr": 128.0, "duration": 300.0}
    result = classify_audio_from_metadata(uuid4(), metadata_raw)
    assert isinstance(result, ExtractorResult)
