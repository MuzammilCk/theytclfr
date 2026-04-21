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

    Reads the yt-dlp info dict format stored by downloader.py.
    yt-dlp stores audio codec at top-level key "acodec" and
    audio bitrate at top-level key "abr" (kbps as float).
    Duration is at top-level key "duration" (float, seconds).

    Pure function — no I/O, no subprocess calls.

    Args:
        metadata_raw: yt-dlp info dict from job.metadata_raw.

    Returns:
        AudioCheckResult with audio stream details.
    """
    # yt-dlp stores acodec as a string like "mp4a.40.2",
    # "opus", "vorbis", or the literal string "none" when
    # no audio stream is present.
    acodec = metadata_raw.get("acodec")
    has_audio = (
        acodec is not None and isinstance(acodec, str) and acodec.lower() != "none"
    )

    if not has_audio:
        return AudioCheckResult(
            has_audio=False,
            audio_codec=None,
            audio_bitrate_kbps=None,
            likely_music=False,
        )

    # abr = audio bitrate in kbps as a float (yt-dlp field).
    # May be None if yt-dlp could not determine it.
    abr_raw = metadata_raw.get("abr")
    audio_bitrate_kbps: float | None = None
    if abr_raw is not None:
        try:
            audio_bitrate_kbps = float(abr_raw)
        except (ValueError, TypeError):
            audio_bitrate_kbps = None

    # yt-dlp subtitles are stored as a dict at key
    # "subtitles". Auto-generated captions are at
    # "automatic_captions". For the music heuristic we
    # only treat manually-added subtitles as a disqualifier
    # because auto-captions appear on almost all videos.
    subtitles = metadata_raw.get("subtitles")
    has_manual_subtitles = isinstance(subtitles, dict) and len(subtitles) > 0

    # Music heuristic — TUNABLE:
    # High bitrate audio + no manually-added subtitles.
    # Duration gate intentionally removed: ringtones (<60s),
    # YouTube Shorts, and long concert recordings are all
    # valid music content. Duration is evaluated in the
    # classifier where it is visible, tested, and logged.
    likely_music = (  # TUNABLE
        audio_bitrate_kbps is not None
        and audio_bitrate_kbps >= 128  # TUNABLE
        and not has_manual_subtitles
    )

    return AudioCheckResult(
        has_audio=True,
        audio_codec=acodec,
        audio_bitrate_kbps=audio_bitrate_kbps,
        likely_music=likely_music,
    )
