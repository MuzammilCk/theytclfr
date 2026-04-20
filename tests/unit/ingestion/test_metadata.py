import json
from unittest.mock import MagicMock, patch

import pytest

from ytclfr.ingestion.metadata import MetadataError, extract_metadata


@pytest.fixture
def dummy_video(tmp_path):
    v = tmp_path / "dummy.mp4"
    v.touch()
    return v


@patch("ytclfr.ingestion.metadata.subprocess.run")
def test_extract_metadata_success(mock_run, dummy_video):
    mock_result = MagicMock()
    mock_result.stdout = json.dumps(
        {
            "format": {"duration": "120.5", "size": "1048576"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30000/1001",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
        }
    )
    mock_run.return_value = mock_result

    metadata = extract_metadata(dummy_video)
    assert metadata.duration_seconds == 120.5
    assert metadata.file_size_bytes == 1048576
    assert metadata.width == 1920
    assert metadata.height == 1080
    assert metadata.video_codec == "h264"
    assert metadata.audio_codec == "aac"
    assert 29.9 < metadata.frame_rate < 30.0


@patch("ytclfr.ingestion.metadata.subprocess.run")
def test_extract_metadata_missing_duration(mock_run, dummy_video):
    mock_result = MagicMock()
    mock_result.stdout = json.dumps({"format": {}, "streams": []})
    mock_run.return_value = mock_result

    with pytest.raises(MetadataError, match="Duration not found"):
        extract_metadata(dummy_video)


@patch("ytclfr.ingestion.metadata.subprocess.run")
def test_extract_metadata_ffprobe_not_found(mock_run, dummy_video):
    mock_run.side_effect = FileNotFoundError()

    with pytest.raises(MetadataError, match="ffprobe not found"):
        extract_metadata(dummy_video)
