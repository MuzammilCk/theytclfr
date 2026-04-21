"""Tests for the audio checker module."""

from ytclfr.router.audio_checker import AudioCheckResult, check_audio_from_metadata


def test_returns_no_audio_when_no_audio_stream():
    """Test that no-audio result is returned for video-only streams."""
    metadata_raw = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264"}
        ]
    }
    result = check_audio_from_metadata(metadata_raw)
    assert isinstance(result, AudioCheckResult)
    assert result.has_audio is False
    assert result.audio_codec is None
    assert result.audio_bitrate_kbps is None
    assert result.likely_music is False


def test_detects_audio_stream():
    """Test that audio stream is detected with correct codec and bitrate."""
    metadata_raw = {
        "streams": [
            {"codec_type": "audio", "codec_name": "aac",
             "bit_rate": "192000"}
        ]
    }
    result = check_audio_from_metadata(metadata_raw)
    assert result.has_audio is True
    assert result.audio_codec == "aac"
    assert result.audio_bitrate_kbps == 192.0


def test_handles_missing_metadata_gracefully():
    """Test that empty metadata returns safe defaults."""
    result = check_audio_from_metadata({})
    assert isinstance(result, AudioCheckResult)
    assert result.has_audio is False
    assert result.audio_codec is None
    assert result.audio_bitrate_kbps is None
    assert result.likely_music is False
