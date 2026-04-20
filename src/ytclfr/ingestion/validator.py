import re
from urllib.parse import urlparse


def validate_youtube_url(url: str) -> str:
    if not url:
        raise ValueError("URL cannot be empty")

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    valid_domains = {"youtube.com", "youtu.be"}
    if domain not in valid_domains:
        raise ValueError("Not a valid YouTube domain")

    path = parsed.path.lower()

    if "/live/" in path:
        raise ValueError("Live streams are out of scope")
    if "/shorts/" in path:
        raise ValueError("Shorts are out of scope")
    if path == "/playlist" or "/playlist" in path:
        raise ValueError("Playlists are out of scope")

    video_id = None

    if domain == "youtu.be":
        video_id = parsed.path.lstrip("/")
    else:
        if path == "/watch":
            query = parsed.query
            match = re.search(r"(?:^|&)v=([^&]+)", query)
            if match:
                video_id = match.group(1)

    if not video_id:
        raise ValueError("Could not extract video ID")

    if len(video_id) != 11:
        raise ValueError("Video ID must be exactly 11 characters")

    return f"https://www.youtube.com/watch?v={video_id}"
