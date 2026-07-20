"""Visual probe — motion, face, text, and format detection for Stage A.

Probes a video file for visual signals: motion score, scene cuts,
face presence, burned-in text, aspect ratio, and content format.

Uses ffmpeg for fast O(1) sampling and OpenCV (cv2) for visual analysis. CPU-only.
All thresholds are TUNABLE module-level constants.
"""

import logging
import subprocess
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ── TUNABLE CONSTANTS ───────────────────────────────────────────────
SAMPLE_FRAME_COUNT: int = 30
FACE_SAMPLE_COUNT: int = 10
FACE_MIN_POSITIVE_FRAMES: int = 3
CUT_THRESHOLD_MULTIPLIER: float = 3.0
TEXT_REGION_MIN_FRAMES: int = 5
TEXT_BAR_BOTTOM_FRACTION: float = 0.20
COLOR_VARIANCE_ANIMATION_THRESHOLD: float = 800.0
SCREEN_RECORDING_MOTION_MAX: float = 0.10
SCREEN_RECORDING_CUT_MAX: int = 3
VISUAL_PROBE_TIMEOUT_SECONDS: int = 90
MOTION_NORMALISE_MAX: float = 50.0

@dataclass
class VisualProbeResult:
    """Result of visual probing for Stage A."""
    has_faces: bool
    has_burned_in_text: bool
    motion_score: float
    motion_density: float
    scene_cut_count: int
    aspect_ratio: str
    content_format: Literal[
        "live_action",
        "animation",
        "screen_recording",
        "mixed",
        "unknown",
    ]
    frame_count_sampled: int
    confidence: float
    sampled_frames: list[Any] = field(default_factory=list)

def probe_visual(
    video_path: str,
    timeout_seconds: int = VISUAL_PROBE_TIMEOUT_SECONDS,
    retain_frames: bool = True,
) -> VisualProbeResult:
    """Probe a video file for visual signals.

    Returns VisualProbeResult. Never raises — failures produce
    safe defaults with reduced confidence.
    """
    try:
        return _probe_visual_inner(video_path, timeout_seconds, retain_frames)
    except subprocess.TimeoutExpired:
        logger.error("Visual probe timed out for %s", video_path)
        return _safe_default()
    except Exception as exc:
        logger.error("Visual probe unexpected failure for %s: %s", video_path, exc, exc_info=True)
        return _safe_default()

def _safe_default() -> VisualProbeResult:
    return VisualProbeResult(
        has_faces=False,
        has_burned_in_text=False,
        motion_score=0.0,
        motion_density=0.0,
        scene_cut_count=0,
        aspect_ratio="unknown",
        content_format="unknown",
        frame_count_sampled=0,
        confidence=0.1,
    )

def _probe_visual_inner(
    video_path: str,
    timeout_seconds: int,
    retain_frames: bool,
) -> VisualProbeResult:
    """Core visual probing logic using ffmpeg pipe. All state is stack-local."""
    import cv2

    # ── Step 1 — Probe video and extract basic metadata ────────
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "csv=p=0",
        video_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=timeout_seconds/3.0)
    if result.returncode != 0 or not result.stdout.strip():
        return _safe_default()

    parts = result.stdout.strip().split("\n")[0].split(",")
    try:
        width = int(parts[0])
        height = int(parts[1])
        duration_s = float(parts[2]) if len(parts) > 2 else 60.0
    except (IndexError, ValueError):
        return _safe_default()

    ratio = width / height if height > 0 else 0
    if 1.70 <= ratio <= 1.82:
        aspect_ratio = "16:9"
    elif 0.54 <= ratio <= 0.58:
        aspect_ratio = "9:16"
    elif 0.95 <= ratio <= 1.05:
        aspect_ratio = "1:1"
    else:
        aspect_ratio = f"{width}:{height}"

    # ── Step 2 — Sample frames evenly using ffmpeg pipe ────────
    target_fps = max(0.1, SAMPLE_FRAME_COUNT / max(1.0, duration_s))
    
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={target_fps}",
        "-frames:v", str(SAMPLE_FRAME_COUNT),
        "-f", "image2pipe",
        "-pix_fmt", "bgr24",
        "-vcodec", "rawvideo",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout_seconds)
    raw = proc.stdout
    frame_size = width * height * 3
    frames = []
    
    if frame_size > 0:
        for i in range(0, len(raw), frame_size):
            chunk = raw[i:i + frame_size]
            if len(chunk) == frame_size:
                frame = np.frombuffer(chunk, dtype=np.uint8).reshape((height, width, 3))
                frames.append(frame)

    if len(frames) < 2:
        return VisualProbeResult(
            has_faces=False,
            has_burned_in_text=False,
            motion_score=0.0,
            motion_density=0.0,
            scene_cut_count=0,
            aspect_ratio=aspect_ratio,
            content_format="unknown",
            frame_count_sampled=len(frames),
            confidence=0.1,
        )

    # ── Step 3 — Motion score (frame differencing) ────────────
    diffs: list[float] = []
    for i in range(len(frames) - 1):
        diff = cv2.absdiff(
            cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY),
            cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY),
        )
        diffs.append(float(diff.mean()))

    mean_diff = float(sum(diffs) / len(diffs)) if diffs else 0.0
    motion_score = float(round(min(mean_diff / MOTION_NORMALISE_MAX, 1.0), 3))

    # ── Step 4 — Scene cut detection ──────────────────────────
    cut_threshold = mean_diff * CUT_THRESHOLD_MULTIPLIER
    cuts = int(sum(1 for d in diffs if d > cut_threshold) if cut_threshold > 0 else 0)
    scene_cut_count = cuts
    duration_minutes = float(duration_s / 60.0) or 1.0
    motion_density = float(round(cuts / duration_minutes, 2))

    # ── Step 5 — Face detection (CPU Haar cascade) ────────────
    # Wrapped independently: OpenCV 5.x removed cv2.CascadeClassifier,
    # and this step running before text/format detection meant a
    # failure here was silently killing every other signal in this
    # function via the outer exception handler in probe_visual().
    has_faces = False
    try:
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        face_sample_count = min(FACE_SAMPLE_COUNT, len(frames))
        face_frame_indices = [
            int(i * len(frames) / face_sample_count)
            for i in range(face_sample_count)
        ]
        positive_face_frames = 0
        for idx in face_frame_indices:
            if idx < len(frames):
                gray = cv2.cvtColor(frames[idx], cv2.COLOR_BGR2GRAY)
                detected = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30),
                )
                if len(detected) > 0:
                    positive_face_frames += 1
        has_faces = bool(positive_face_frames >= FACE_MIN_POSITIVE_FRAMES)
    except Exception as exc:
        logger.warning("Face detection unavailable, defaulting to no faces: %s", exc)

    # ── Step 6 — Burned-in text detection ─────────────────────
    # Previously a Canny-edge "wide contour" heuristic looking only at
    # the bottom 20% of the frame — built for subtitle bars, not title
    # cards, and empirically doesn't fire on real rendered text at all
    # (verified against a synthetic countdown video: 0/30 frames, even
    # checked across the whole frame, not just the bottom strip).
    # Actually running OCR on a subset of sampled frames is more
    # reliable than guessing from edge geometry, and it's the same
    # extractor already used for real extraction — no new dependency.
    positive_text_frames = 0
    TEXT_OCR_SAMPLE_STRIDE: int = 3  # check every 3rd frame — bounded cost
    TEXT_OCR_MIN_CONFIDENCE: float = 0.4
    try:
        from ytclfr.extractors.ocr_extractor import extract_text_from_frame_v2
        checked = 0
        for frame in frames[::TEXT_OCR_SAMPLE_STRIDE]:
            checked += 1
            text, conf = extract_text_from_frame_v2(frame)
            if text.strip() and conf >= TEXT_OCR_MIN_CONFIDENCE:
                positive_text_frames += 1
        # scale the frame-count threshold down to match the strided sample
        adaptive_text_min = max(1, min(TEXT_REGION_MIN_FRAMES, checked) // 2)
    except Exception as exc:
        logger.warning("Text detection via OCR failed, defaulting to no text: %s", exc)
        adaptive_text_min = 1

    has_burned_in_text = bool(positive_text_frames >= adaptive_text_min)

    # ── Step 7 — content_format heuristic ─────────────────────
    screen_recording = (
        motion_score < SCREEN_RECORDING_MOTION_MAX
        and aspect_ratio == "16:9"
        and scene_cut_count <= SCREEN_RECORDING_CUT_MAX
    )
    animation = False
    COLOR_HIST_BINS: int = 8
    COLOR_HIST_RANGE_MAX: int = 256
    ANIMATION_SAMPLE_LIMIT: int = 10

    if not screen_recording:
        color_variances: list[float] = []
        for frame in frames[:ANIMATION_SAMPLE_LIMIT]:
            hist = cv2.calcHist(
                [frame], [0, 1, 2], None,
                [COLOR_HIST_BINS, COLOR_HIST_BINS, COLOR_HIST_BINS],
                [0, COLOR_HIST_RANGE_MAX, 0, COLOR_HIST_RANGE_MAX, 0, COLOR_HIST_RANGE_MAX],
            )
            color_variances.append(float(hist.var()))
        avg_variance = sum(color_variances) / len(color_variances) if color_variances else 0.0
        animation = avg_variance < COLOR_VARIANCE_ANIMATION_THRESHOLD

    if screen_recording:
        content_format = "screen_recording"
    elif animation:
        content_format = "animation"
    else:
        content_format = "live_action"

    # ── Step 8 — Confidence score and return ──────────────────
    HALF_SAMPLE: int = SAMPLE_FRAME_COUNT // 2
    base_confidence: float = 0.75
    if len(frames) < HALF_SAMPLE:
        base_confidence = 0.50

    return VisualProbeResult(
        has_faces=has_faces,
        has_burned_in_text=has_burned_in_text,
        motion_score=motion_score,
        motion_density=motion_density,
        scene_cut_count=scene_cut_count,
        aspect_ratio=aspect_ratio,
        content_format=content_format,
        frame_count_sampled=len(frames),
        confidence=float(base_confidence),
        sampled_frames=frames if retain_frames else [],
    )
