import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp

from ytclfr.core.config import Settings
from ytclfr.core.logging import get_logger

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
        self._cookies_file: Path | None = (
            Path(settings.ytdlp_cookies_file) if settings.ytdlp_cookies_file else None
        )

    def _validate_cookies(self) -> None:
        if self._cookies_file is None:
            return
        if not self._cookies_file.exists():
            raise IngestionError(
                f"Cookies file not found: "
                f"{self._cookies_file}. "
                "Export Firefox cookies: close Firefox, "
                "visit youtube.com logged in, then run: "
                "yt-dlp --cookies-from-browser firefox "
                "--cookies cookies.txt "
                '"https://youtu.be/jNQXAC9IVRw"'
            )
        if self._cookies_file.stat().st_size == 0:
            raise IngestionError(
                f"Cookies file is empty: "
                f"{self._cookies_file}. "
                "Re-export cookies from Firefox."
            )

    def download(self, url: str, job_id: uuid.UUID, output_dir: Path) -> DownloadResult:
        self._validate_cookies()

        logger.debug(f"Starting download for {url} into {output_dir}")

        target_dir = output_dir / str(job_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts_info: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": {"node": {}},
        }
        if self._cookies_file is not None:
            ydl_opts_info["cookiefile"] = str(self._cookies_file)

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
                    raise IngestionError(
                        "YouTube bot detection triggered. "
                        "Cookies missing, expired, or invalid. "
                        "Close Firefox, visit youtube.com logged "
                        "in, then run: yt-dlp "
                        "--cookies-from-browser firefox "
                        "--cookies cookies.txt "
                        '"https://youtu.be/jNQXAC9IVRw"'
                    ) from exc
                raise IngestionError(
                    f"Video unavailable or private: {error_msg}"
                ) from exc

        ydl_opts_download: dict[str, Any] = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": str(target_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": {"node": {}},
        }
        if self._cookies_file is not None:
            ydl_opts_download["cookiefile"] = str(self._cookies_file)

        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            try:
                result_info = ydl.extract_info(url, download=True)
                result_info = ydl.sanitize_info(result_info)
            except Exception as e:
                raise IngestionError(f"Download failed: {e}") from e

        files = list(target_dir.glob("*"))
        if not files:
            raise IngestionError("Download succeeded but no files found")

        video_path = files[0]

        return DownloadResult(
            video_path=video_path,
            audio_path=None,
            title=result_info.get("title", "Unknown Title"),
            channel=result_info.get("uploader", "Unknown Channel"),
            duration_seconds=float(result_info.get("duration", 0.0)),
            thumbnail_url=result_info.get("thumbnail"),
            metadata_raw=result_info,
        )
