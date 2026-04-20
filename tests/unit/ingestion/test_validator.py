import pytest
from ytclfr.ingestion.validator import validate_youtube_url

def test_validate_youtube_url_accepts_standard():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcW"
    assert validate_youtube_url(url) == url

def test_validate_youtube_url_accepts_no_www():
    url = "https://youtube.com/watch?v=dQw4w9WgXcW"
    assert validate_youtube_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcW"

def test_validate_youtube_url_accepts_short():
    url = "https://youtu.be/dQw4w9WgXcW"
    assert validate_youtube_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcW"

def test_validate_youtube_url_rejects_vimeo():
    with pytest.raises(ValueError):
        validate_youtube_url("https://vimeo.com/123456")

def test_validate_youtube_url_rejects_live():
    with pytest.raises(ValueError):
        validate_youtube_url("https://www.youtube.com/live/abc12345678")

def test_validate_youtube_url_rejects_shorts():
    with pytest.raises(ValueError):
        validate_youtube_url("https://www.youtube.com/shorts/abc123def45")

def test_validate_youtube_url_rejects_playlist():
    with pytest.raises(ValueError):
        validate_youtube_url("https://www.youtube.com/playlist?list=XYZ")

def test_validate_youtube_url_rejects_not_a_url():
    with pytest.raises(ValueError):
        validate_youtube_url("not_a_url_at_all")

def test_validate_youtube_url_rejects_empty():
    with pytest.raises(ValueError):
        validate_youtube_url("")

def test_validate_youtube_url_rejects_short_video_id():
    with pytest.raises(ValueError):
        validate_youtube_url("https://www.youtube.com/watch?v=short")
