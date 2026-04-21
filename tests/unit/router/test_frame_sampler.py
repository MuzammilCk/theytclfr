"""Tests for the frame sampler module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ytclfr.router.frame_sampler import (
    FrameSamplerError,
    SampledFrames,
    sample_frames,
)


def _mock_ffprobe_result(duration: float = 60.0) -> MagicMock:
    """Create a mock subprocess result for ffprobe."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps({"format": {"duration": str(duration)}})
    result.stderr = ""
    return result


def _mock_ffmpeg_success(tmp_path: Path) -> MagicMock:
    """Create a side_effect that creates frame files on ffmpeg calls."""

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        # If this is an ffmpeg call (not ffprobe), create the output file
        if cmd and cmd[0] == "ffmpeg":
            # The output path is the last argument
            output_path = Path(cmd[-1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"\xff\xd8\xff\xe0")  # JPEG header
            result = MagicMock()
            result.returncode = 0
            return result
        # ffprobe call
        return _mock_ffprobe_result()

    return side_effect


@patch("ytclfr.router.frame_sampler.subprocess.run")
def test_sample_frames_returns_correct_count(mock_run, tmp_path):
    """Test that sample_frames returns the requested number of frames."""
    fake_video = tmp_path / "video.mp4"
    fake_video.touch()
    output_dir = tmp_path / "frames"

    mock_run.side_effect = _mock_ffmpeg_success(tmp_path)

    result = sample_frames(fake_video, output_dir, 3)

    assert isinstance(result, SampledFrames)
    assert result.sample_count == 3
    assert len(result.frame_paths) == 3
    assert result.video_duration_seconds == 60.0


@patch("ytclfr.router.frame_sampler.subprocess.run")
def test_sample_frames_raises_on_ffprobe_failure(mock_run, tmp_path):
    """Test that FrameSamplerError is raised when ffprobe is not found."""
    fake_video = tmp_path / "video.mp4"
    fake_video.touch()
    output_dir = tmp_path / "frames"

    mock_run.side_effect = FileNotFoundError("ffprobe not found")

    with pytest.raises(FrameSamplerError, match="ffprobe not found"):
        sample_frames(fake_video, output_dir, 3)


@patch("ytclfr.router.frame_sampler.subprocess.run")
def test_sample_frames_raises_when_no_frames(mock_run, tmp_path):
    """Test FrameSamplerError when ffprobe succeeds but no frames extracted."""
    fake_video = tmp_path / "video.mp4"
    fake_video.touch()
    output_dir = tmp_path / "frames"

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if cmd and cmd[0] == "ffprobe":
            return _mock_ffprobe_result()
        # ffmpeg fails — no files created
        result = MagicMock()
        result.returncode = 1
        return result

    mock_run.side_effect = side_effect

    with pytest.raises(FrameSamplerError, match="No frames"):
        sample_frames(fake_video, output_dir, 3)
