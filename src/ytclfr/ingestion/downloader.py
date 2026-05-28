import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp

from ytclfr.core.config import Settings
from ytclfr.core.logging import get_logger
from ytclfr.ingestion.cookie_pool import CookiePool

logger = get_logger(__name__)


class IngestionError(Exception):
    pass


@dataclass
class DownloadResult:
    video_path: Path
    audio_path: Path | None
    title: str
    channel: str
    duration_seconds: float
    thumbnail_url: str | None
    metadata_raw: dict[str, Any]


class VideoDownloader:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cookie_pool = CookiePool(settings)

    def _get_cookie_file(self) -> Path | None:
        cookie_file = self.cookie_pool.get_cookie()
        if cookie_file is None:
            return None
        if not cookie_file.exists():
            raise IngestionError(
                f"Cookies file not found: {cookie_file}. "
                "Ensure yt-dlp cookies are provided."
            )
        if cookie_file.stat().st_size == 0:
            raise IngestionError(
                f"Cookies file is empty: {cookie_file}. "
                "Re-export cookies."
            )
        return cookie_file

    def download(self, url: str, job_id: uuid.UUID, output_dir: Path) -> DownloadResult:
        cookie_file = self._get_cookie_file()

        logger.debug(f"Starting download for {url} into {output_dir}")

        target_dir = output_dir / str(job_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts_info: Any = {
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": {"node": {}},
        }
        if cookie_file is not None:
            ydl_opts_info["cookiefile"] = str(cookie_file)

        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise IngestionError("Could not extract video info")
            except Exception as exc:
                error_msg = str(exc)
                if any(
                    kw in error_msg
                    for kw in [
                        "Sign in to confirm",
                        "not a bot",
                        "LOGIN_REQUIRED",
                    ]
                ):
                    if cookie_file is not None:
                        self.cookie_pool.mark_exhausted(cookie_file)
                    raise IngestionError(
                        "YouTube bot detection triggered. "
                        "Cookies missing, expired, or invalid. "
                        "Close Firefox, visit youtube.com logged "
                        "in, then run: yt-dlp "
                        "--cookies-from-browser firefox "
                        "--cookies cookies.txt "
                        '"https://youtu.be/jNQXAC9IVRw"'
                    ) from exc
                if "unavailable" in error_msg.lower() or "private" in error_msg.lower():
                    raise IngestionError(
                        f"Video unavailable or private: {error_msg}"
                    ) from exc
                # Let other exceptions (like ConnectionResetError) bubble up for Celery retry
                raise

        ydl_opts_download: Any = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": str(target_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": {"node": {}},
        }
        if cookie_file is not None:
            ydl_opts_download["cookiefile"] = str(cookie_file)

        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            try:
                extracted = ydl.extract_info(url, download=True)
            except Exception as exc:
                error_msg = str(exc)
                if any(kw in error_msg for kw in ["Sign in to confirm", "not a bot", "LOGIN_REQUIRED"]):
                    if cookie_file is not None:
                        self.cookie_pool.mark_exhausted(cookie_file)
                raise IngestionError(f"Download failed: {exc}") from exc
            result_info: Any = ydl.sanitize_info(extracted or info) or {}

        files = list(target_dir.glob("*"))
        if not files:
            raise IngestionError("Download succeeded but no files found")

        video_path = files[0]

        # Prune massive yt-dlp fields to prevent DB bloat and Celery serialization overhead
        # but PRESERVE the keys for subtitles and automatic_captions so that
        # probing.metadata_probe still detects them.
        keys_to_remove = ["formats", "thumbnails", "heatmap"]
        pruned_metadata = {k: v for k, v in result_info.items() if k not in keys_to_remove}
        
        # Shrink subtitles and captions down to just the language keys
        if "subtitles" in pruned_metadata and isinstance(pruned_metadata["subtitles"], dict):
            pruned_metadata["subtitles"] = {
                lang: [True] for lang in pruned_metadata["subtitles"] if pruned_metadata["subtitles"][lang]
            }
            
        if "automatic_captions" in pruned_metadata and isinstance(pruned_metadata["automatic_captions"], dict):
            pruned_metadata["automatic_captions"] = {
                lang: [True] for lang in pruned_metadata["automatic_captions"] if pruned_metadata["automatic_captions"][lang]
            }

        return DownloadResult(
            video_path=video_path,
            audio_path=None,
            title=pruned_metadata.get("title", "Unknown Title"),
            channel=pruned_metadata.get("uploader", "Unknown Channel"),
            duration_seconds=float(pruned_metadata.get("duration", 0.0)),
            thumbnail_url=result_info.get("thumbnail"),
            metadata_raw=pruned_metadata,
        )
