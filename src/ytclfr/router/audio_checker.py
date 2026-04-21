"""Check audio presence and type from video metadata."""

from dataclasses import dataclass
from typing import Any


@dataclass
class AudioCheckResult:
    """Result of audio stream analysis."""

    has_audio: bool
    audio_codec: str | None
    audio_bitrate_kbps: float | None
    likely_music: bool


def check_audio_from_metadata(
    metadata_raw: dict[str, Any],
) -> AudioCheckResult:
    """Determine audio presence and type from metadata_raw.

    Inspects the streams list in metadata_raw for audio codec
    information. Uses a loose heuristic for music detection based
    on bitrate, subtitle absence, and duration range.

    Pure function — no I/O, no subprocess calls.

    Args:
        metadata_raw: Raw metadata dictionary (from ffprobe or yt-dlp).

    Returns:
        AudioCheckResult with audio stream details.
    """
    streams = metadata_raw.get("streams", [])
    if not isinstance(streams, list):
        streams = []

    # Find first audio stream
    audio_stream: dict[str, Any] | None = None
    has_subtitle_stream = False

    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = stream.get("codec_type", "")
        if codec_type == "audio" and audio_stream is None:
            audio_stream = stream
        if codec_type == "subtitle":
            has_subtitle_stream = True

    if audio_stream is None:
        return AudioCheckResult(
            has_audio=False,
            audio_codec=None,
            audio_bitrate_kbps=None,
            likely_music=False,
        )

    # Extract codec and bitrate
    audio_codec = audio_stream.get("codec_name")
    audio_bitrate_kbps: float | None = None

    bit_rate_raw = audio_stream.get("bit_rate")
    if bit_rate_raw is not None:
        try:
            audio_bitrate_kbps = float(bit_rate_raw) / 1000
        except (ValueError, TypeError):
            audio_bitrate_kbps = None

    # Music heuristic:
    #   High audio bitrate (>= 128 kbps),
    #   no subtitle streams,
    #   duration between 60 and 600 seconds
    duration: float | None = None
    format_data = metadata_raw.get("format", {})
    if isinstance(format_data, dict):
        dur_raw = format_data.get("duration")
        if dur_raw is not None:
            try:
                duration = float(dur_raw)
            except (ValueError, TypeError):
                duration = None

    likely_music = (
        audio_bitrate_kbps is not None
        and audio_bitrate_kbps >= 128
        and not has_subtitle_stream
        and duration is not None
        and 60 <= duration <= 600
    )

    return AudioCheckResult(
        has_audio=True,
        audio_codec=audio_codec,
        audio_bitrate_kbps=audio_bitrate_kbps,
        likely_music=likely_music,
    )
