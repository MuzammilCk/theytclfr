"""Tests for the audio checker module.

All inputs use yt-dlp info dict format, which is the actual
format stored in job.metadata_raw by downloader.py.
yt-dlp keys: acodec (str), abr (float kbps), duration
(float seconds), subtitles (dict).
"""

from ytclfr.router.audio_checker import check_audio_from_metadata


def test_returns_no_audio_when_acodec_is_none():
    """yt-dlp sets acodec=None when no audio stream."""
    result = check_audio_from_metadata({"acodec": None})
    assert result.has_audio is False
    assert result.likely_music is False
    assert result.audio_bitrate_kbps is None


def test_returns_no_audio_when_acodec_is_string_none():
    """yt-dlp sets acodec='none' (string) for video-only."""
    result = check_audio_from_metadata({"acodec": "none"})
    assert result.has_audio is False
    assert result.likely_music is False


def test_detects_audio_stream_with_aac():
    """Standard MP4 with AAC audio at high bitrate."""
    result = check_audio_from_metadata(
        {
            "acodec": "mp4a.40.2",
            "abr": 192.0,
            "duration": 240.0,
        }
    )
    assert result.has_audio is True
    assert result.audio_codec == "mp4a.40.2"
    assert result.audio_bitrate_kbps == 192.0


def test_likely_music_high_bitrate_no_subtitles():
    """High bitrate audio with no manual subtitles."""
    result = check_audio_from_metadata(
        {
            "acodec": "opus",
            "abr": 160.0,
            "duration": 210.0,
            "subtitles": {},
        }
    )
    assert result.has_audio is True
    assert result.likely_music is True


def test_likely_music_true_for_short_ringtone():
    """A 20-second ringtone must be detected as music.
    This is the regression test for the original bug.
    """
    result = check_audio_from_metadata(
        {
            "acodec": "mp4a.40.2",
            "abr": 192.0,
            "duration": 20.0,
            "subtitles": {},
        }
    )
    assert result.has_audio is True
    assert result.likely_music is True


def test_not_likely_music_when_low_bitrate():
    """Low bitrate audio (speech) should not trigger music."""
    result = check_audio_from_metadata(
        {
            "acodec": "mp4a.40.2",
            "abr": 64.0,
            "duration": 300.0,
        }
    )
    assert result.has_audio is True
    assert result.likely_music is False


def test_not_likely_music_when_manual_subtitles_present():
    """Manual subtitles disqualify the music heuristic."""
    result = check_audio_from_metadata(
        {
            "acodec": "opus",
            "abr": 192.0,
            "duration": 240.0,
            "subtitles": {"en": [{"url": "..."}]},
        }
    )
    assert result.has_audio is True
    assert result.likely_music is False


def test_auto_captions_do_not_disqualify_music():
    """Auto-generated captions should not block music routing.
    automatic_captions is ignored in the music heuristic.
    """
    result = check_audio_from_metadata(
        {
            "acodec": "opus",
            "abr": 192.0,
            "duration": 240.0,
            "subtitles": {},
            "automatic_captions": {"en": [{"url": "..."}]},
        }
    )
    assert result.has_audio is True
    assert result.likely_music is True


def test_handles_missing_metadata_gracefully():
    """Empty dict must not raise and must return no audio."""
    result = check_audio_from_metadata({})
    assert result.has_audio is False
    assert result.likely_music is False
    assert result.audio_bitrate_kbps is None


def test_handles_malformed_abr_gracefully():
    """Non-numeric abr must not raise."""
    result = check_audio_from_metadata(
        {
            "acodec": "mp4a.40.2",
            "abr": "not_a_number",
            "duration": 200.0,
        }
    )
    assert result.has_audio is True
    assert result.audio_bitrate_kbps is None
    assert result.likely_music is False
