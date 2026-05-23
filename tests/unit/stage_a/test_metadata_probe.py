"""Unit tests for metadata_probe.py."""

import json

import pytest

from ytclfr.probing.metadata_probe import probe_metadata


class TestMetadataProbe:
    """Tests for probe_metadata function."""

    def test_parses_subtitle_track_present(
        self, tmp_path: object
    ) -> None:
        """Subtitle keys in JSON → has_subtitle_track=True."""
        data = {
            "duration": 300,
            "width": 1920,
            "height": 1080,
            "subtitles": {"en": [{"url": "..."}]},
            "automatic_captions": {},
            "chapters": [],
            "tags": [],
            "title": "Test",
            "upload_date": "20250101",
        }
        f = tmp_path / "video.info.json"  # type: ignore
        f.write_text(json.dumps(data))
        result = probe_metadata(str(f))
        assert result.has_subtitle_track is True
        assert result.language == "en"
        assert result.aspect_ratio == "16:9"
        assert result.duration_seconds == 300.0
        assert result.confidence == 0.95

    def test_raises_on_missing_file(self) -> None:
        """Non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            probe_metadata("/nonexistent/path/video.info.json")

    def test_raises_on_malformed_json(
        self, tmp_path: object
    ) -> None:
        """Malformed JSON raises ValueError."""
        f = tmp_path / "bad.info.json"  # type: ignore
        f.write_text("{not valid json")
        with pytest.raises(ValueError):
            probe_metadata(str(f))

    def test_aspect_ratio_vertical(
        self, tmp_path: object
    ) -> None:
        """9:16 video width/height → aspect_ratio='9:16'."""
        data = {
            "duration": 60,
            "width": 1080,
            "height": 1920,
            "subtitles": {},
            "automatic_captions": {},
            "chapters": [],
            "tags": [],
            "title": "Short",
            "upload_date": None,
        }
        f = tmp_path / "v.info.json"  # type: ignore
        f.write_text(json.dumps(data))
        result = probe_metadata(str(f))
        assert result.aspect_ratio == "9:16"

    def test_missing_duration_defaults_to_zero(
        self, tmp_path: object
    ) -> None:
        """Missing duration field → duration_seconds=0.0."""
        data = {
            "width": 1920,
            "height": 1080,
            "subtitles": {},
            "automatic_captions": {},
            "chapters": [],
            "tags": [],
            "title": "NoTime",
            "upload_date": None,
        }
        f = tmp_path / "nd.info.json"  # type: ignore
        f.write_text(json.dumps(data))
        result = probe_metadata(str(f))
        assert result.duration_seconds == 0.0

    def test_aspect_ratio_square(
        self, tmp_path: object
    ) -> None:
        """1:1 video width/height → aspect_ratio='1:1'."""
        data = {
            "duration": 30,
            "width": 1080,
            "height": 1080,
            "subtitles": {},
            "automatic_captions": {},
            "chapters": [],
            "tags": [],
            "title": "Square",
            "upload_date": None,
        }
        f = tmp_path / "sq.info.json"  # type: ignore
        f.write_text(json.dumps(data))
        result = probe_metadata(str(f))
        assert result.aspect_ratio == "1:1"

    def test_chapters_detected(
        self, tmp_path: object
    ) -> None:
        """Multiple chapters → has_chapters=True."""
        data = {
            "duration": 600,
            "width": 1920,
            "height": 1080,
            "subtitles": {},
            "automatic_captions": {},
            "chapters": [
                {"start_time": 0, "end_time": 120, "title": "Intro"},
                {"start_time": 120, "end_time": 600, "title": "Main"},
            ],
            "tags": ["python", "tutorial"],
            "title": "Chaptered Video",
            "upload_date": "20250115",
        }
        f = tmp_path / "ch.info.json"  # type: ignore
        f.write_text(json.dumps(data))
        result = probe_metadata(str(f))
        assert result.has_chapters is True
        assert result.chapter_count == 2
        assert result.tags == ["python", "tutorial"]

    def test_no_subtitles_no_captions(
        self, tmp_path: object
    ) -> None:
        """Empty subtitles/captions → both False."""
        data = {
            "duration": 120,
            "width": 1280,
            "height": 720,
            "subtitles": {},
            "automatic_captions": {},
            "chapters": [],
            "tags": [],
            "title": "Basic",
            "upload_date": None,
        }
        f = tmp_path / "basic.info.json"  # type: ignore
        f.write_text(json.dumps(data))
        result = probe_metadata(str(f))
        assert result.has_subtitle_track is False
        assert result.has_auto_captions is False
        assert result.language is None
