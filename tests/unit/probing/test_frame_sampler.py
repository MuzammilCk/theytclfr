"""Tests for probing/frame_sampler.py (probe_visual).

This function previously had zero test coverage. Covers two real bugs
found via an actual synthetic-video integration test (not mocked):

1. Face detection (Step 5) crashed on any OpenCV 5.x install
   (cv2.CascadeClassifier was removed), which killed the entire probe
   via the outer exception handler in probe_visual() — meaning motion,
   scene-cut, and text detection (Step 6, right after) never ran either.
2. The burned-in-text heuristic (wide-contour edge detection on the
   bottom 20% of the frame) never actually fired on real rendered
   text — verified empirically at 0/30 frames on a synthetic
   countdown video, even checking the whole frame. Replaced with
   real OCR via the already-fixed extract_text_from_frame_v2.
"""
import os
from unittest.mock import MagicMock
import numpy as np
import pytest
from ytclfr.probing.frame_sampler import probe_visual

WIDTH, HEIGHT = 64, 48
SYNTH_VIDEO = "/home/claude/synth_video/countdown_video2.mp4"


def _mock_subprocess_sequence(mocker, num_frames=10):
    """Mocks the real two-call sequence: ffprobe (returns csv metadata)
    then ffmpeg (returns a raw BGR24 frame stream on stdout)."""
    probe_result = MagicMock(returncode=0, stdout=f"{WIDTH},{HEIGHT},30.0\n")
    frame = np.random.randint(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8)
    ffmpeg_result = MagicMock(stdout=frame.tobytes() * num_frames)
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = [probe_result, ffmpeg_result]
    return mock_run


class TestFaceDetectionFaultTolerance:

    def test_missing_cascade_classifier_degrades_gracefully(self, mocker):
        _mock_subprocess_sequence(mocker)
        mocker.patch(
            "ytclfr.extractors.ocr_extractor.extract_text_from_frame_v2",
            return_value=("", 0.0),
        )

        result = probe_visual("/fake/video.mp4", retain_frames=False)

        assert result.has_faces is False
        # the function must still complete with real values, not
        # silently fall through to the safe-default (confidence=0.1,
        # frame_count_sampled=0) that a full crash would produce
        assert result.frame_count_sampled > 0
        assert result.confidence > 0.1


class TestBurnedInTextDetection:

    def test_real_ocr_text_marks_has_burned_in_text(self, mocker):
        _mock_subprocess_sequence(mocker, num_frames=9)
        mocker.patch(
            "ytclfr.extractors.ocr_extractor.extract_text_from_frame_v2",
            return_value=("10 The Matrix", 0.95),
        )

        result = probe_visual("/fake/video.mp4", retain_frames=False)

        assert result.has_burned_in_text is True

    def test_no_text_found_leaves_has_burned_in_text_false(self, mocker):
        _mock_subprocess_sequence(mocker)
        mocker.patch(
            "ytclfr.extractors.ocr_extractor.extract_text_from_frame_v2",
            return_value=("", 0.0),
        )

        result = probe_visual("/fake/video.mp4", retain_frames=False)

        assert result.has_burned_in_text is False

    def test_low_confidence_ocr_does_not_count_as_text(self, mocker):
        """A confidence below the threshold shouldn't count — avoids
        false positives from OCR noise on textureless frames."""
        _mock_subprocess_sequence(mocker)
        mocker.patch(
            "ytclfr.extractors.ocr_extractor.extract_text_from_frame_v2",
            return_value=("garbled", 0.1),
        )

        result = probe_visual("/fake/video.mp4", retain_frames=False)

        assert result.has_burned_in_text is False

    def test_ocr_failure_during_text_detection_degrades_gracefully(self, mocker):
        _mock_subprocess_sequence(mocker)
        mocker.patch(
            "ytclfr.extractors.ocr_extractor.extract_text_from_frame_v2",
            side_effect=RuntimeError("OCR engine crashed"),
        )

        result = probe_visual("/fake/video.mp4", retain_frames=False)

        # must not raise, must still return a usable result
        assert result.has_burned_in_text is False
        assert result.frame_count_sampled > 0


def test_real_synthetic_countdown_video_end_to_end():
    """Integration test against a real rendered video with actual
    burned-in title-card text — the exact scenario that silently
    failed before (crash + broken heuristic), verified here against
    the real ffmpeg/cv2/tesseract stack, not mocks."""
    if not os.path.exists(SYNTH_VIDEO):
        pytest.skip("synthetic test video not available in this environment")

    result = probe_visual(SYNTH_VIDEO, retain_frames=False)

    assert result.has_burned_in_text is True
    assert result.frame_count_sampled > 0
    assert result.confidence > 0.1
