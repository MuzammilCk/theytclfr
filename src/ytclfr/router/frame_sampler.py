"""Extract evenly-spaced frames from a video file via ffmpeg subprocess."""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


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

    Uses ffprobe to determine duration, then ffmpeg to extract
    individual frames at calculated timestamps.

    Args:
        video_path: Path to the video file.
        output_dir: Directory to save extracted JPEG frames.
        sample_count: Number of frames to extract.

    Returns:
        SampledFrames with paths to extracted frames.

    Raises:
        FrameSamplerError: If ffprobe fails or no frames extracted.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration via ffprobe
    duration = _get_video_duration(video_path)

    # Calculate evenly-spaced timestamps
    interval = duration / (sample_count + 1)
    timestamps = [interval * i for i in range(1, sample_count + 1)]

    # Extract frames at each timestamp
    frame_paths: list[Path] = []
    for i, timestamp in enumerate(timestamps):
        frame_path = output_dir / f"frame_{i:03d}.jpg"
        success = _extract_frame(video_path, timestamp, frame_path)
        if success:
            frame_paths.append(frame_path)
        else:
            logger.debug(
                "Failed to extract frame %d at %.2fs from %s",
                i,
                timestamp,
                video_path,
            )

    if not frame_paths:
        raise FrameSamplerError(
            f"No frames could be extracted from {video_path}. "
            f"Attempted {sample_count} frames over {duration:.1f}s duration."
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
            f"for {video_path}: {result.stderr}"
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


def _extract_frame(
    video_path: Path, timestamp: float, output_path: Path
) -> bool:
    """Extract a single frame at the given timestamp.

    Returns True if the frame was successfully extracted.
    """
    cmd = [
        "ffmpeg",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return result.returncode == 0 and output_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
