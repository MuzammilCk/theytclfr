import pytest
import uuid
from unittest.mock import patch, MagicMock
from pathlib import Path
from ytclfr.ingestion.downloader import VideoDownloader, IngestionError
from ytclfr.core.config import Settings

@pytest.fixture
def mock_settings():
    return Settings(
        database_url="sqlite://",
        redis_url="redis://",
        groq_api_key="fake",
        jwt_secret_key="fake"
    )

@patch("ytclfr.ingestion.downloader.yt_dlp.YoutubeDL")
def test_downloader_success(mock_yt_dlp, mock_settings, tmp_path):
    mock_instance_info = MagicMock()
    mock_instance_download = MagicMock()
    
    mock_instance_info.extract_info.return_value = {"id": "123"}
    
    mock_instance_download.extract_info.return_value = {
        "title": "Test Video",
        "uploader": "Test Channel",
        "duration": 120.5,
        "thumbnail": "http://example.com/thumb.jpg",
        "id": "123"
    }
    
    job_id = uuid.uuid4()
    mock_yt_dlp.side_effect = [mock_instance_info, mock_instance_download]
    
    downloader = VideoDownloader(mock_settings)
    
    target_dir = tmp_path / str(job_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    fake_video = target_dir / "Test Video.mp4"
    fake_video.touch()
    
    result = downloader.download("https://youtube.com/watch?v=abc123def45", job_id, tmp_path)
    
    assert result.title == "Test Video"
    assert result.channel == "Test Channel"
    assert result.duration_seconds == 120.5
    assert result.video_path == fake_video
    assert result.thumbnail_url == "http://example.com/thumb.jpg"

@patch("ytclfr.ingestion.downloader.yt_dlp.YoutubeDL")
def test_downloader_private_video(mock_yt_dlp, mock_settings, tmp_path):
    mock_instance = MagicMock()
    mock_instance.extract_info.side_effect = Exception("Private video")
    mock_yt_dlp.return_value.__enter__.return_value = mock_instance
    
    downloader = VideoDownloader(mock_settings)
    with pytest.raises(IngestionError, match="Video unavailable or private"):
        downloader.download("https://youtube.com/watch?v=abc123def45", uuid.uuid4(), tmp_path)

@patch("ytclfr.ingestion.downloader.yt_dlp.YoutubeDL")
def test_downloader_unavailable_video(mock_yt_dlp, mock_settings, tmp_path):
    mock_instance = MagicMock()
    mock_instance.extract_info.side_effect = Exception("Video is unavailable")
    mock_yt_dlp.return_value.__enter__.return_value = mock_instance
    
    downloader = VideoDownloader(mock_settings)
    with pytest.raises(IngestionError, match="Video unavailable or private"):
        downloader.download("https://youtube.com/watch?v=abc123def45", uuid.uuid4(), tmp_path)

@patch("ytclfr.ingestion.downloader.yt_dlp.YoutubeDL")
def test_downloader_download_failure(mock_yt_dlp, mock_settings, tmp_path):
    mock_instance_info = MagicMock()
    mock_instance_info.extract_info.return_value = {"id": "123"}
    
    mock_instance_download = MagicMock()
    mock_instance_download.extract_info.side_effect = Exception("Generic yt-dlp error")
    
    mock_yt_dlp.side_effect = [mock_instance_info, mock_instance_download]
    
    downloader = VideoDownloader(mock_settings)
    with pytest.raises(IngestionError, match="Download failed"):
        downloader.download("https://youtube.com/watch?v=abc123def45", uuid.uuid4(), tmp_path)
