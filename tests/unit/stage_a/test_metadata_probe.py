"""Unit tests for metadata_probe.py."""

import json

import pytest

from ytclfr.probing.metadata_probe import probe_metadata, probe_metadata_dict


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


class TestMetadataDictProbe:
    """Tests for probe_metadata_dict function."""

    def test_dict_probe_parses_full_metadata(self) -> None:
        """Full valid dict with all fields → correct result."""
        data = {
            "duration": 300,
            "width": 1920,
            "height": 1080,
            "subtitles": {"en": [{"url": "..."}]},
            "automatic_captions": {"en": [{"url": "..."}]},
            "chapters": [
                {"start_time": 0, "end_time": 120, "title": "Intro"},
                {"start_time": 120, "end_time": 300, "title": "Main"},
            ],
            "tags": ["python", "tutorial"],
            "title": "Full Video",
            "upload_date": "20250101",
        }
        result = probe_metadata_dict(data)
        assert result.duration_seconds == 300.0
        assert result.aspect_ratio == "16:9"
        assert result.has_subtitle_track is True
        assert result.language == "en"
        assert result.has_auto_captions is True
        assert result.has_chapters is True
        assert result.chapter_count == 2
        assert result.tags == ["python", "tutorial"]
        assert result.title == "Full Video"
        assert result.upload_date == "20250101"
        assert result.confidence == 0.95

    def test_dict_probe_empty_dict(self) -> None:
        """Empty dict {} → safe defaults everywhere."""
        result = probe_metadata_dict({})
        assert result.duration_seconds == 0.0
        assert result.aspect_ratio == "unknown"
        assert result.has_subtitle_track is False
        assert result.has_auto_captions is False
        assert result.language is None
        assert result.has_chapters is False
        assert result.chapter_count == 0
        assert result.tags == []
        assert result.title == ""
        assert result.upload_date is None

    def test_dict_probe_missing_subtitles(self) -> None:
        """No subtitles key → has_subtitle_track=False, language=None."""
        data = {
            "duration": 60,
            "width": 1920,
            "height": 1080,
            "automatic_captions": {},
            "chapters": [],
            "tags": [],
            "title": "No Subs",
        }
        result = probe_metadata_dict(data)
        assert result.has_subtitle_track is False
        assert result.language is None

    def test_dict_probe_aspect_ratio_vertical(self) -> None:
        """width=1080, height=1920 → aspect_ratio='9:16'."""
        data = {"width": 1080, "height": 1920}
        result = probe_metadata_dict(data)
        assert result.aspect_ratio == "9:16"

    def test_dict_probe_aspect_ratio_square(self) -> None:
        """width=1080, height=1080 → aspect_ratio='1:1'."""
        data = {"width": 1080, "height": 1080}
        result = probe_metadata_dict(data)
        assert result.aspect_ratio == "1:1"

    def test_dict_probe_chapters_detected(self) -> None:
        """2+ chapters → has_chapters=True, correct count."""
        data = {
            "chapters": [
                {"start_time": 0, "end_time": 100, "title": "Ch1"},
                {"start_time": 100, "end_time": 200, "title": "Ch2"},
                {"start_time": 200, "end_time": 300, "title": "Ch3"},
            ],
        }
        result = probe_metadata_dict(data)
        assert result.has_chapters is True
        assert result.chapter_count == 3

    def test_dict_probe_no_chapters(self) -> None:
        """Empty chapters list → has_chapters=False."""
        data = {"chapters": []}
        result = probe_metadata_dict(data)
        assert result.has_chapters is False
        assert result.chapter_count == 0

    def test_dict_probe_none_values(self) -> None:
        """Dict with None values for all optional fields → safe defaults."""
        data = {
            "duration": None,
            "width": None,
            "height": None,
            "subtitles": None,
            "automatic_captions": None,
            "chapters": None,
            "tags": None,
            "title": None,
            "upload_date": None,
        }
        result = probe_metadata_dict(data)
        assert result.duration_seconds == 0.0
        assert result.aspect_ratio == "unknown"
        assert result.has_subtitle_track is False
        assert result.has_auto_captions is False
        assert result.language is None
        assert result.has_chapters is False
        assert result.chapter_count == 0
        assert result.tags == []
        assert result.title == ""
        assert result.upload_date is None

    def test_dict_probe_confidence_always_095(self) -> None:
        """Confidence is always 0.95 regardless of input."""
        assert probe_metadata_dict({}).confidence == 0.95
        assert probe_metadata_dict({"duration": 100}).confidence == 0.95
        assert probe_metadata_dict({"title": "X"}).confidence == 0.95

    def test_dict_probe_auto_captions(self) -> None:
        """automatic_captions present → has_auto_captions=True."""
        data = {
            "automatic_captions": {"en": [{"url": "..."}]},
            "subtitles": {},
        }
        result = probe_metadata_dict(data)
        assert result.has_auto_captions is True
        assert result.has_subtitle_track is False
