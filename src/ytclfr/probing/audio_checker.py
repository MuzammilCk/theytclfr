"""Audio probe — VAD + music detection for Stage A Signal Census.

Probes an audio file for speech, music, and basic metadata.
Uses webrtcvad for voice activity detection and librosa for
beat-tracking / spectral-centroid music detection.

All thresholds are TUNABLE module-level constants.
This function never raises — all failures produce safe defaults.

Note: On Windows, signal.alarm() is unavailable; we use
threading-based timeout instead.
"""

import json
import logging
import subprocess
import threading
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

# ── TUNABLE CONSTANTS (at module top, never inline) ─────────────────
VAD_FRAME_DURATION_MS: int = 30
VAD_SPEECH_THRESHOLD: float = 0.20  # voiced frame ratio → has_speech
VAD_AGGRESSIVENESS: int = 2  # webrtcvad mode 0–3
MUSIC_MIN_BPM: float = 60.0
MUSIC_MAX_BPM: float = 200.0
MUSIC_BITRATE_FALLBACK_BPS: int = 192_000
AUDIO_PROBE_TIMEOUT_SECONDS: int = 60


@dataclass
class AudioProbeResult:
    """Result of audio probing for Stage A."""

    has_speech: bool
    has_music: bool
    audio_type: Literal[
        "speech_only",
        "music_only",
        "speech_music",
        "sfx",
        "ambient",
        "silent",
    ]  # one of the SignalManifest audio_type literals
    language: str | None
    duration_seconds: float
    confidence: float


class _TimeoutError(Exception):
    """Internal timeout signal for probe_audio."""


def probe_audio(
    audio_path: str,
    metadata: dict | None = None,
    timeout_seconds: int = AUDIO_PROBE_TIMEOUT_SECONDS,
) -> AudioProbeResult:
    """Probe an audio file for speech, music, and basic metadata.

    Returns AudioProbeResult. Never raises — all failures produce
    a safe default result with low confidence.
    """
    # Use a threading event for timeout on Windows
    timeout_event = threading.Event()
    timer = threading.Timer(
        timeout_seconds, lambda: timeout_event.set()
    )
    timer.daemon = True
    timer.start()

    try:
        return _probe_audio_inner(
            audio_path, metadata, timeout_event
        )
    except _TimeoutError:
        logger.warning(
            "Audio probe timed out after %ds for %s",
            timeout_seconds,
            audio_path,
        )
        return AudioProbeResult(
            has_speech=False,
            has_music=False,
            audio_type="ambient",
            language=None,
            duration_seconds=0.0,
            confidence=0.2,
        )
    except Exception as exc:
        logger.error(
            "Audio probe unexpected failure for %s: %s",
            audio_path,
            exc,
            exc_info=True,
        )
        return AudioProbeResult(
            has_speech=False,
            has_music=False,
            audio_type="ambient",
            language=None,
            duration_seconds=0.0,
            confidence=0.1,
        )
    finally:
        timer.cancel()


def _check_timeout(timeout_event: threading.Event) -> None:
    """Raise _TimeoutError if the timeout has fired."""
    if timeout_event.is_set():
        raise _TimeoutError("Audio probe timed out")


def _probe_audio_inner(
    audio_path: str,
    metadata: dict | None,
    timeout_event: threading.Event,
) -> AudioProbeResult:
    """Core audio probing logic, separated for timeout wrapping."""

    # ── Step 4.2 — Fast metadata via ffprobe subprocess ─────────
    duration: float = 0.0
    bit_rate: int = 0
    codec_name: str = ""
    ffprobe_ok: bool = False

    try:
        ffprobe_result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                audio_path,
            ],
            capture_output=True,
            timeout=30,
        )
        probe_data = json.loads(ffprobe_result.stdout)
        fmt = probe_data.get("format", {})
        duration = float(fmt.get("duration") or 0.0)
        bit_rate = int(fmt.get("bit_rate") or 0)
        streams = probe_data.get("streams", [])
        for stream in streams:
            if stream.get("codec_type") == "audio":
                codec_name = stream.get("codec_name", "")
                break
        ffprobe_ok = True
    except Exception as exc:
        logger.warning(
            "ffprobe failed for %s: %s — continuing with defaults",
            audio_path,
            exc,
        )
        duration = 0.0
        bit_rate = 0
        codec_name = ""
        ffprobe_ok = False

    _check_timeout(timeout_event)

    # Short audio — classify as silent immediately
    # Only use high confidence if ffprobe actually succeeded
    SILENT_DURATION_THRESHOLD: float = 1.0  # noqa: N806
    if duration < SILENT_DURATION_THRESHOLD:
        silent_confidence = 1.0 if ffprobe_ok else 0.3
        return AudioProbeResult(
            audio_type="silent",
            has_speech=False,
            has_music=False,
            language=None,
            duration_seconds=duration,
            confidence=silent_confidence,
        )


    # ── Step 4.3 — Voice Activity Detection via webrtcvad ───────
    has_speech: bool = False
    speech_confidence: float = 0.4

    try:
        import webrtcvad

        vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        pcm_result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-i",
                audio_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "s16le",
                "-",
                "-loglevel",
                "quiet",
            ],
            capture_output=True,
            timeout=60,
        )
        pcm_data = pcm_result.stdout

        # Frame size: 16kHz * 2 bytes * (duration_ms / 1000)
        frame_size = int(
            16000 * 2 * VAD_FRAME_DURATION_MS / 1000
        )
        total_frames = len(pcm_data) // frame_size
        voiced_frames = 0

        for i in range(total_frames):
            start = i * frame_size
            frame = pcm_data[start : start + frame_size]
            if len(frame) == frame_size:
                try:
                    if vad.is_speech(frame, 16000):
                        voiced_frames += 1
                except Exception:
                    continue

        if total_frames > 0:
            ratio = voiced_frames / total_frames
            has_speech = ratio >= VAD_SPEECH_THRESHOLD
            speech_confidence = min(
                ratio / VAD_SPEECH_THRESHOLD, 1.0
            )
        else:
            has_speech = False
            speech_confidence = 0.3

    except ImportError:
        logger.warning(
            "webrtcvad not installed — speech detection skipped"
        )
        has_speech = False
        speech_confidence = 0.4
    except Exception as exc:
        logger.error("VAD failed: %s", exc, exc_info=True)
        has_speech = False
        speech_confidence = 0.3

    _check_timeout(timeout_event)

    # ── Step 4.4 — Music detection ──────────────────────────────
    has_music: bool = False
    music_confidence: float = 0.5

    try:
        import warnings
        import librosa
        import numpy as np

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            y, sr = librosa.load(
                audio_path, sr=None, mono=True, duration=60.0
            )
        tempo_result = librosa.beat.beat_track(y=y, sr=sr)
        # librosa may return tempo as array or scalar
        tempo_val = tempo_result[0]
        if isinstance(tempo_val, np.ndarray):
            tempo_val = float(tempo_val.item())
        else:
            tempo_val = float(tempo_val)

        centroid = librosa.feature.spectral_centroid(
            y=y, sr=sr
        ).mean()
        CENTROID_MUSIC_THRESHOLD: float = 1000.0  # noqa: N806
        has_music = (
            MUSIC_MIN_BPM <= tempo_val <= MUSIC_MAX_BPM
            and centroid > CENTROID_MUSIC_THRESHOLD
        )
        music_confidence = 0.8 if has_music else 0.7
    except ImportError:
        logger.warning(
            "librosa not installed — using bitrate fallback"
        )
        has_music = bit_rate > MUSIC_BITRATE_FALLBACK_BPS
        music_confidence = 0.5
    except Exception as exc:
        logger.error(
            "Music detection failed: %s", exc, exc_info=True
        )
        has_music = False
        music_confidence = 0.3

    _check_timeout(timeout_event)

    # ── Step 4.5 — Language detection ───────────────────────────
    language: str | None = None
    if metadata is not None:
        subtitles = metadata.get("subtitles", {})
        if subtitles:
            language = next(iter(subtitles.keys()), None)
    # STAGE-B-TODO: ASR-detected language replaces this None
    #               when tasks/stage_b.py runs run_asr

    # ── Step 4.6 — Classify audio_type ──────────────────────────
    if has_speech and has_music:
        audio_type = "speech_music"
    elif has_speech:
        audio_type = "speech_only"
    elif has_music:
        audio_type = "music_only"
    elif duration > SILENT_DURATION_THRESHOLD:
        audio_type = "ambient"
    else:
        audio_type = "silent"

    # ── Step 4.7 — Compute overall confidence ───────────────────
    confidence = round(
        (speech_confidence + music_confidence) / 2.0, 3
    )

    # ── Step 4.8 — Return result ────────────────────────────────
    return AudioProbeResult(
        has_speech=has_speech,
        has_music=has_music,
        audio_type=audio_type,
        language=language,
        duration_seconds=duration,
        confidence=confidence,
    )
