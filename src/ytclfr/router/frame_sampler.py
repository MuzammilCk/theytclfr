"""Extract evenly-spaced frames from a video file via ffmpeg subprocess.

Uses a single ffmpeg call instead of N separate calls, reducing
subprocess overhead from O(N) to O(1).
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ytclfr.core.logging import get_logger

logger = get_logger(__name__)


class FrameSamplerError(Exception):
    """Raised when frame sampling fails."""
    pass


@dataclass
class SampledFrames:
    """Result of frame sampling operation."""

    frame_paths: list[Path]
    video_duration_seconds: float
    sample_count: int


def sample_frames(
    video_path: Path,
    output_dir: Path,
    sample_count: int,
) -> SampledFrames:
    """Extract N evenly-spaced frames from a video file.

    Uses a single ffmpeg call with the fps filter to extract all
    frames in one subprocess, eliminating the O(N) subprocess
    overhead of calling ffmpeg once per frame.

    Args:
        video_path: Path to the video file.
        output_dir: Directory to save extracted JPEG frames.
        sample_count: Number of frames to extract.

    Returns:
        SampledFrames with paths to extracted frames and duration.

    Raises:
        FrameSamplerError: If ffprobe fails or no frames extracted.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    duration = _get_video_duration(video_path)

    if duration <= 0:
        raise FrameSamplerError(
            f"Video {video_path} has zero or negative duration: "
            f"{duration}s"
        )

    # Calculate the fps value needed to extract exactly sample_count
    # frames evenly distributed across the video.
    # fps = sample_count / duration gives one frame every
    # (duration / sample_count) seconds.
    fps_value = sample_count / duration

    output_pattern = str(output_dir / "frame_%03d.jpg")

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"fps={fps_value:.6f}",
        "-frames:v", str(sample_count),
        "-q:v", "2",
        "-y",
        output_pattern,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise FrameSamplerError(
            "ffmpeg not found. Ensure ffmpeg is installed and in PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FrameSamplerError(
            f"ffmpeg timed out extracting frames from {video_path}"
        ) from exc

    if result.returncode != 0:
        logger.warning(
            "ffmpeg frame extraction returned non-zero exit code %d "
            "for %s: %s",
            result.returncode,
            video_path,
            result.stderr[:500],
        )

    frame_paths = sorted(output_dir.glob("frame_*.jpg"))

    if not frame_paths:
        raise FrameSamplerError(
            f"No frames could be extracted from {video_path}. "
            f"Attempted {sample_count} frames over {duration:.1f}s. "
            f"ffmpeg stderr: {result.stderr[:300] if result else 'N/A'}"
        )

    logger.debug(
        "Extracted %d frames from %s (%.1fs duration, target=%d)",
        len(frame_paths),
        video_path.name,
        duration,
        sample_count,
    )

    return SampledFrames(
        frame_paths=frame_paths,
        video_duration_seconds=duration,
        sample_count=len(frame_paths),
    )


def _get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe.

    Raises:
        FrameSamplerError: If ffprobe fails or duration cannot be parsed.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(video_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise FrameSamplerError(
            "ffprobe not found. Ensure ffmpeg is installed and in PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FrameSamplerError(
            f"ffprobe timed out reading {video_path}"
        ) from exc

    if result.returncode != 0:
        raise FrameSamplerError(
            f"ffprobe failed with code {result.returncode} "
            f"for {video_path}: {result.stderr[:300]}"
        )

    try:
        probe_data = json.loads(result.stdout)
        duration_str = probe_data["format"]["duration"]
        return float(duration_str)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise FrameSamplerError(
            f"Could not parse video duration from ffprobe output "
            f"for {video_path}: {exc}"
        ) from exc
