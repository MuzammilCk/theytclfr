"""Unit tests for audio_checker.py (probe_audio)."""

import json
from unittest.mock import MagicMock, patch

from ytclfr.probing.audio_checker import AudioProbeResult, probe_audio


class TestAudioProbe:
    """Tests for probe_audio function."""

    @patch("ytclfr.probing.audio_checker.subprocess.run")
    def test_silent_audio_detected(
        self, mock_run: MagicMock
    ) -> None:
        """Duration < 1.0s → audio_type='silent'."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "format": {
                        "duration": "0.5",
                        "bit_rate": "0",
                    },
                    "streams": [{"codec_name": "aac", "codec_type": "audio"}],
                }
            ).encode(),
            returncode=0,
        )
        result = probe_audio("/fake/audio.m4a")
        assert result.audio_type == "silent"
        assert result.confidence == 1.0

    @patch("ytclfr.probing.audio_checker.subprocess.run")
    def test_ffprobe_failure_returns_safe_default(
        self, mock_run: MagicMock
    ) -> None:
        """ffprobe failure → safe default, confidence < 0.5."""
        mock_run.side_effect = OSError("ffprobe not found")
        result = probe_audio("/fake/audio.m4a")
        assert result.audio_type in {
            "ambient",
            "silent",
            "speech_only",
            "music_only",
            "speech_music",
            "sfx",
        }
        assert result.confidence < 0.5

    def test_probe_audio_never_raises(self) -> None:
        """probe_audio with a non-existent path must not raise."""
        result = probe_audio("/definitely/does/not/exist.m4a")
        assert isinstance(result, AudioProbeResult)

    @patch("ytclfr.probing.audio_checker.subprocess.run")
    def test_returns_audio_probe_result_type(
        self, mock_run: MagicMock
    ) -> None:
        """Return type must always be AudioProbeResult."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "format": {
                        "duration": "120.0",
                        "bit_rate": "128000",
                    },
                    "streams": [
                        {"codec_name": "opus", "codec_type": "audio"}
                    ],
                }
            ).encode(),
            returncode=0,
        )
        result = probe_audio("/fake/audio.m4a")
        assert isinstance(result, AudioProbeResult)
        assert result.duration_seconds == 120.0
