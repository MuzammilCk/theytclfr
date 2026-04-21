from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ytclfr.contracts.extractor import (
    ASRSegment,
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
    ASRSegment with text = "speech" or "music" and
    confidence from the heuristic.

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
        ExtractorResult with extractor_type="asr" containing
        a single segment whose text is "speech" or "music".
    """
    audio = check_audio_from_metadata(metadata_raw)

    if not audio.has_audio:
        label = "no_audio"
        confidence = 0.95
    elif audio.likely_music:
        label = "music"
        confidence = 0.80
    else:
        label = "speech"
        confidence = 0.70

    segment = ASRSegment(
        segment_type="asr",
        start_time=0.0,
        end_time=0.0,
        text=label,
        confidence=confidence,
        words=[],
    )

    return ExtractorResult(
        job_id=job_id,
        extractor_type="asr",
        segments=[segment],
        total_duration_seconds=float(metadata_raw.get("duration", 0.0) or 0.0),
        extracted_at=datetime.now(UTC),
        error=None,
    )
