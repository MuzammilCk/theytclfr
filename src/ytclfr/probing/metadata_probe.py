"""Metadata probe — parse yt-dlp .info.json for signal metadata.

Zero ML. Zero subprocesses. Zero external dependencies beyond
Python stdlib (json, os, logging, dataclasses).
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MetadataProbeResult:
    """Result of metadata probing from a yt-dlp .info.json file."""

    duration_seconds: float
    aspect_ratio: str
    has_subtitle_track: bool
    has_auto_captions: bool
    language: str | None
    has_chapters: bool
    chapter_count: int
    tags: list[str]
    title: str
    upload_date: str | None
    confidence: float  # always 0.95 — metadata is reliable


def probe_metadata(metadata_json_path: str) -> MetadataProbeResult:
    """Parse a yt-dlp .info.json file and extract signal metadata.

    Raises:
        FileNotFoundError: if the .info.json path does not exist.
        ValueError: if the file is not valid JSON.
    Never suppresses these — the caller (stage_a.py) handles them.
    All other field failures degrade gracefully to safe defaults.
    """
    # Step 6.1 — Load JSON
    if not os.path.exists(metadata_json_path):
        raise FileNotFoundError(
            f"yt-dlp metadata not found: {metadata_json_path}"
        )
    with open(metadata_json_path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in metadata file: {exc}"
            ) from exc

    # Step 6.2 — Extract duration
    duration_seconds = float(data.get("duration") or 0.0)

    # Step 6.3 — Compute aspect_ratio from width/height
    width = data.get("width") or 0
    height = data.get("height") or 0
    if width > 0 and height > 0:
        ratio = width / height
        if 1.70 <= ratio <= 1.82:
            aspect_ratio = "16:9"
        elif 0.54 <= ratio <= 0.58:
            aspect_ratio = "9:16"
        elif 0.95 <= ratio <= 1.05:
            aspect_ratio = "1:1"
        else:
            aspect_ratio = f"{width}:{height}"
    else:
        aspect_ratio = "unknown"

    # Step 6.4 — Subtitle and caption detection
    subtitles = data.get("subtitles") or {}
    automatic_captions = data.get("automatic_captions") or {}
    has_subtitle_track = bool(
        subtitles and any(v for v in subtitles.values())
    )
    has_auto_captions = bool(
        automatic_captions
        and any(v for v in automatic_captions.values())
    )
    language = (
        next(iter(subtitles.keys()), None) if subtitles else None
    )

    # Step 6.5 — Chapters
    chapters = data.get("chapters") or []
    has_chapters = len(chapters) > 1
    chapter_count = len(chapters)

    # Step 6.6 — Tags, title, upload_date
    tags = [str(t) for t in (data.get("tags") or [])]
    title = str(data.get("title") or "")
    upload_date = data.get("upload_date")

    # Step 6.7 — Return
    return MetadataProbeResult(
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        has_subtitle_track=has_subtitle_track,
        has_auto_captions=has_auto_captions,
        language=language,
        has_chapters=has_chapters,
        chapter_count=chapter_count,
        tags=tags,
        title=title,
        upload_date=str(upload_date) if upload_date else None,
        confidence=0.95,
    )


def probe_metadata_dict(data: dict[str, Any]) -> MetadataProbeResult:
    """Parse a metadata dictionary and extract signal metadata.

    Accepts the raw yt-dlp metadata dict (job.metadata_raw from
    PostgreSQL) directly, eliminating any file-on-disk dependency.

    Unlike probe_metadata(), this function never raises.
    All field failures degrade gracefully to safe defaults.

    Args:
        data: The raw yt-dlp info dict stored in job.metadata_raw.

    Returns:
        MetadataProbeResult with confidence=0.95.
    """
    # Duration
    duration_seconds = float(data.get("duration") or 0.0)

    # Aspect ratio from width/height
    width = data.get("width") or 0
    height = data.get("height") or 0
    if width > 0 and height > 0:
        ratio = width / height
        if 1.70 <= ratio <= 1.82:
            aspect_ratio = "16:9"
        elif 0.54 <= ratio <= 0.58:
            aspect_ratio = "9:16"
        elif 0.95 <= ratio <= 1.05:
            aspect_ratio = "1:1"
        else:
            aspect_ratio = f"{width}:{height}"
    else:
        aspect_ratio = "unknown"

    # Subtitle and caption detection
    subtitles = data.get("subtitles") or {}
    automatic_captions = data.get("automatic_captions") or {}
    has_subtitle_track = bool(
        subtitles and any(v for v in subtitles.values())
    )
    has_auto_captions = bool(
        automatic_captions
        and any(v for v in automatic_captions.values())
    )
    language = (
        next(iter(subtitles.keys()), None) if subtitles else None
    )

    # Chapters
    chapters = data.get("chapters") or []
    has_chapters = len(chapters) > 1
    chapter_count = len(chapters)

    # Tags, title, upload_date
    tags = [str(t) for t in (data.get("tags") or [])]
    title = str(data.get("title") or "")
    upload_date = data.get("upload_date")

    return MetadataProbeResult(
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        has_subtitle_track=has_subtitle_track,
        has_auto_captions=has_auto_captions,
        language=language,
        has_chapters=has_chapters,
        chapter_count=chapter_count,
        tags=tags,
        title=title,
        upload_date=str(upload_date) if upload_date else None,
        confidence=0.95,
    )

