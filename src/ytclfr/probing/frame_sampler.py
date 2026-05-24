"""Visual probe — motion, face, text, and format detection for Stage A.

Probes a video file for visual signals: motion score, scene cuts,
face presence, burned-in text, aspect ratio, and content format.

Uses OpenCV (cv2) for all visual analysis. CPU-only, no GPU required.
All thresholds are TUNABLE module-level constants.
This function never raises — all failures produce safe defaults.

Thread-safe: all intermediate state is stack-local.
No module-level globals are written during probe execution.
"""

import logging
import threading
from dataclasses import dataclass
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


def probe_visual(
    video_path: str,
    timeout_seconds: int = VISUAL_PROBE_TIMEOUT_SECONDS,
) -> VisualProbeResult:
    """Probe a video file for visual signals.

    Returns VisualProbeResult. Never raises — failures produce
    safe defaults with reduced confidence.

    Thread-safe: no module-level state is written.
    Concurrent calls on different threads do not interfere.
    """
    timeout_event = threading.Event()
    timer = threading.Timer(
        timeout_seconds, lambda: timeout_event.set()
    )
    timer.daemon = True
    timer.start()

    try:
        return _probe_visual_inner(video_path, timeout_event)
    except Exception as exc:
        logger.error(
            "Visual probe unexpected failure for %s: %s",
            video_path,
            exc,
            exc_info=True,
        )
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
    finally:
        timer.cancel()


def _probe_visual_inner(
    video_path: str,
    timeout_event: threading.Event,
) -> VisualProbeResult:
    """Core visual probing logic. All state is stack-local.

    Checks timeout_event.is_set() between major steps and returns
    a VisualProbeResult built from locally computed values so far.
    Never writes to module-level globals.
    """
    import cv2

    # ── Initialise all locals to safe defaults ───────────────────
    aspect_ratio: str = "unknown"
    motion_score: float = 0.0
    motion_density: float = 0.0
    scene_cut_count: int = 0
    has_faces: bool = False
    has_burned_in_text: bool = False
    content_format: str = "unknown"
    frames: list[Any] = []
    total_frames: int = 0
    fps: float = 30.0

    def _partial(confidence: float = 0.3) -> VisualProbeResult:
        """Return a VisualProbeResult from current local state."""
        return VisualProbeResult(
            has_faces=has_faces,
            has_burned_in_text=has_burned_in_text,
            motion_score=motion_score,
            motion_density=motion_density,
            scene_cut_count=scene_cut_count,
            aspect_ratio=aspect_ratio,
            content_format=content_format,
            frame_count_sampled=len(frames),
            confidence=confidence,
        )

    # ── Step 5.2 — Open video and extract basic metadata ────────
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
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

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        ratio = width / height if height > 0 else 0
        if 1.70 <= ratio <= 1.82:
            aspect_ratio = "16:9"
        elif 0.54 <= ratio <= 0.58:
            aspect_ratio = "9:16"
        elif 0.95 <= ratio <= 1.05:
            aspect_ratio = "1:1"
        else:
            aspect_ratio = f"{width}:{height}"

        # ── Step 5.3 — Sample frames evenly ─────────────────────
        n = min(SAMPLE_FRAME_COUNT, total_frames)
        if n < 1:
            return VisualProbeResult(
                has_faces=False,
                has_burned_in_text=False,
                motion_score=0.0,
                motion_density=0.0,
                scene_cut_count=0,
                aspect_ratio=aspect_ratio,
                content_format="unknown",
                frame_count_sampled=0,
                confidence=0.1,
            )

        indices = [int(i * total_frames / n) for i in range(n)]
        for idx in indices:
            if timeout_event.is_set():
                return _partial()
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)

    finally:
        cap.release()

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

    if timeout_event.is_set():
        return _partial()

    # ── Step 5.4 — Motion score (frame differencing) ────────────
    diffs: list[float] = []
    for i in range(len(frames) - 1):
        diff = cv2.absdiff(
            cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY),
            cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY),
        )
        diffs.append(float(diff.mean()))

    mean_diff = sum(diffs) / len(diffs) if diffs else 0.0
    motion_score = round(
        min(mean_diff / MOTION_NORMALISE_MAX, 1.0), 3
    )

    if timeout_event.is_set():
        return _partial()

    # ── Step 5.5 — Scene cut detection ──────────────────────────
    cut_threshold = mean_diff * CUT_THRESHOLD_MULTIPLIER
    cuts = (
        sum(1 for d in diffs if d > cut_threshold)
        if cut_threshold > 0
        else 0
    )
    scene_cut_count = cuts
    duration_minutes = (total_frames / fps / 60.0) or 1.0
    motion_density = round(cuts / duration_minutes, 2)

    if timeout_event.is_set():
        return _partial()

    # ── Step 5.6 — Face detection (CPU Haar cascade) ────────────
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades
        + "haarcascade_frontalface_default.xml"
    )
    face_sample_count = min(FACE_SAMPLE_COUNT, len(frames))
    face_frame_indices = [
        int(i * len(frames) / face_sample_count)
        for i in range(face_sample_count)
    ]
    positive_face_frames = 0
    for idx in face_frame_indices:
        if idx < len(frames):
            gray = cv2.cvtColor(
                frames[idx], cv2.COLOR_BGR2GRAY
            )
            detected = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )
            if len(detected) > 0:
                positive_face_frames += 1

    has_faces = positive_face_frames >= FACE_MIN_POSITIVE_FRAMES

    if timeout_event.is_set():
        return _partial()

    # ── Step 5.7 — Burned-in text detection (subtitle bar) ──────
    positive_text_frames = 0
    WIDE_CONTOUR_WIDTH_FRACTION: float = 0.3  # noqa: N806
    WIDE_CONTOUR_MIN_COUNT: int = 2  # noqa: N806
    CANNY_LOW_THRESHOLD: int = 50  # noqa: N806
    CANNY_HIGH_THRESHOLD: int = 150  # noqa: N806

    for frame in frames:
        h = frame.shape[0]
        bar_height = int(h * TEXT_BAR_BOTTOM_FRACTION)
        bottom_strip = frame[h - bar_height : h, :]
        gray = cv2.cvtColor(bottom_strip, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(
            gray, CANNY_LOW_THRESHOLD, CANNY_HIGH_THRESHOLD
        )
        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        wide_contours = [
            c
            for c in contours
            if cv2.boundingRect(c)[2]
            > frame.shape[1] * WIDE_CONTOUR_WIDTH_FRACTION
        ]
        if len(wide_contours) >= WIDE_CONTOUR_MIN_COUNT:
            positive_text_frames += 1

    has_burned_in_text = (
        positive_text_frames >= TEXT_REGION_MIN_FRAMES
    )

    if timeout_event.is_set():
        return _partial()

    # ── Step 5.8 — content_format heuristic ─────────────────────
    screen_recording = (
        motion_score < SCREEN_RECORDING_MOTION_MAX
        and aspect_ratio == "16:9"
        and scene_cut_count <= SCREEN_RECORDING_CUT_MAX
    )
    animation = False
    COLOR_HIST_BINS: int = 8  # noqa: N806
    COLOR_HIST_RANGE_MAX: int = 256  # noqa: N806
    ANIMATION_SAMPLE_LIMIT: int = 10  # noqa: N806

    if not screen_recording:
        color_variances: list[float] = []
        for frame in frames[:ANIMATION_SAMPLE_LIMIT]:
            hist = cv2.calcHist(
                [frame],
                [0, 1, 2],
                None,
                [COLOR_HIST_BINS, COLOR_HIST_BINS, COLOR_HIST_BINS],
                [
                    0,
                    COLOR_HIST_RANGE_MAX,
                    0,
                    COLOR_HIST_RANGE_MAX,
                    0,
                    COLOR_HIST_RANGE_MAX,
                ],
            )
            color_variances.append(float(hist.var()))
        avg_variance = (
            sum(color_variances) / len(color_variances)
            if color_variances
            else 0.0
        )
        animation = (
            avg_variance < COLOR_VARIANCE_ANIMATION_THRESHOLD
        )

    if screen_recording:
        content_format = "screen_recording"
    elif animation:
        content_format = "animation"
    else:
        content_format = "live_action"

    # ── Step 5.9 — Confidence score and return ──────────────────
    HALF_SAMPLE: int = SAMPLE_FRAME_COUNT // 2  # noqa: N806
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
        confidence=base_confidence,
    )
