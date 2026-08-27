from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ytclfr.contracts.extractor import (
    AudioSegment,
    ExtractorResult,
)
from ytclfr.core.logging import get_logger
from ytclfr.router.audio_checker import (
    check_audio_from_metadata,
)

logger = get_logger(__name__)


def classify_audio_from_metadata(
    job_id: UUID,
    metadata_raw: dict[str, Any],
) -> ExtractorResult:
    """Classify audio type using yt-dlp metadata heuristics.

    Wraps the router's AudioCheckResult in an ExtractorResult
    so audio classification fits the standard pipeline
    contract. The classification is stored as a single
    AudioSegment with label = "speech", "music", or "no_audio"
    and confidence from the heuristic.

    This is the V1 heuristic implementation. The function
    signature and return contract are stable — the
    underlying logic can be replaced with YAMNet in V2
    without touching any downstream code.

    # PHASE-9-TODO: Replace metadata heuristic with YAMNet
    # acoustic model for production-grade audio classification.

    Args:
        job_id: UUID of the job being classified.
        metadata_raw: yt-dlp info dict from job.metadata_raw.

    Returns:
        ExtractorResult with extractor_type="audio" containing
        a single AudioSegment with the classification label.
    """
    audio = check_audio_from_metadata(metadata_raw)

    codec = metadata_raw.get("acodec")
    bitrate_raw = metadata_raw.get("abr")
    bitrate_kbps = float(bitrate_raw) if bitrate_raw is not None else None

    if not audio.has_audio:
        label = "no_audio"
        confidence = 0.95
    elif audio.likely_music:
        label = "music"
        confidence = 0.80
    else:
        label = "speech"
        confidence = 0.70

    segment = AudioSegment(
        segment_type="audio",
        label=label,
        confidence=confidence,
        codec=codec if codec != "none" else None,
        bitrate_kbps=bitrate_kbps,
    )

    return ExtractorResult(
        job_id=job_id,
        extractor_type="audio",
        segments=[segment],
        total_duration_seconds=float(metadata_raw.get("duration", 0.0) or 0.0),
        extracted_at=datetime.now(UTC),
        error=None,
    )
