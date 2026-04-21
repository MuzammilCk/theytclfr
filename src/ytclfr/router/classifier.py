"""Combine signals into a RouterDecision conforming to Phase 1 contract."""

from datetime import UTC, datetime
from uuid import UUID

from ytclfr.contracts.router import RouterDecision
from ytclfr.router.audio_checker import AudioCheckResult
from ytclfr.router.metadata_inspector import MetadataSignals

# Confidence thresholds — module-level constants
HIGH_CONFIDENCE: float = 0.85   # TUNABLE
MED_CONFIDENCE: float = 0.65    # TUNABLE
LOW_CONFIDENCE: float = 0.45    # TUNABLE
MIXED_CONFIDENCE: float = 0.40  # TUNABLE


def classify(
    job_id: UUID,
    audio: AudioCheckResult,
    metadata: MetadataSignals,
    frame_count: int,
    video_duration_seconds: float,
) -> RouterDecision:
    """Classify a video into a content route using heuristic rules.

    Classification rules are applied in priority order — first match wins.
    No ML models are used. This is a lightweight, fast classifier.

    Args:
        job_id: UUID of the job being classified.
        audio: Audio check results from metadata analysis.
        metadata: Metadata keyword signals.
        frame_count: Number of frames successfully sampled.
        video_duration_seconds: Video duration in seconds.

    Returns:
        RouterDecision conforming to the Phase 1 contract.
    """
    decided_at = datetime.now(UTC)

    # Rule 1: MUSIC-HEAVY
    if (
        audio.likely_music
        and not metadata.has_list_signal
        and not metadata.has_recipe_signal
    ):
        return RouterDecision(
            job_id=job_id,
            primary_route="music-heavy",
            confidence=HIGH_CONFIDENCE,
            speech_density=0.2,
            ocr_density=0.1,
            decided_at=decided_at,
            routing_notes="High audio bitrate with music heuristic",
        )

    # Rule 2: SLIDE-PRESENTATION
    if metadata.has_slide_signal and not metadata.has_list_signal:
        return RouterDecision(
            job_id=job_id,
            primary_route="slide-presentation",
            confidence=MED_CONFIDENCE,
            speech_density=0.7,
            ocr_density=0.8,
            decided_at=decided_at,
            routing_notes="Slide/lecture keyword in metadata",
        )

    # Rule 3: LIST-EDIT
    if metadata.has_list_signal:
        confidence = (
            HIGH_CONFIDENCE
            if len(metadata.matched_keywords) >= 2
            else MED_CONFIDENCE
        )
        return RouterDecision(
            job_id=job_id,
            primary_route="list-edit",
            confidence=confidence,
            speech_density=0.5,
            ocr_density=0.6,
            decided_at=decided_at,
            routing_notes=f"List keywords: {metadata.matched_keywords[:3]}",
        )

    # Rule 4: RECIPE / SPEECH-HEAVY
    if metadata.has_recipe_signal or (
        audio.has_audio and not audio.likely_music
    ):
        return RouterDecision(
            job_id=job_id,
            primary_route="speech-heavy",
            confidence=MED_CONFIDENCE,
            speech_density=0.8,
            ocr_density=0.2,
            decided_at=decided_at,
            routing_notes="Recipe/speech signal detected",
        )

    # Rule 5: FALLBACK — MIXED
    return RouterDecision(
        job_id=job_id,
        primary_route="mixed",
        confidence=MIXED_CONFIDENCE,
        speech_density=0.5,
        ocr_density=0.5,
        decided_at=decided_at,
        routing_notes="No strong signal detected",
    )
