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

# Minimum duration in seconds for a video to be considered
# a legitimate music track vs an accidental short clip
# or test file. 10 seconds chosen to allow ringtones
# (~20-30s) while filtering out 1-2s test files.
MUSIC_MIN_DURATION_SECONDS: float = 10.0  # TUNABLE


def classify(
    job_id: UUID,
    audio: AudioCheckResult,
    metadata: MetadataSignals,
    frame_count: int,
    video_duration_seconds: float,
) -> RouterDecision:
    """Classify a video into a content route using heuristics.

    Classification rules are applied in priority order —
    first match wins. No ML models are used.

    Rule priority rationale:
      1. Music-heavy: audio signal is the strongest physical
         evidence and takes priority over title keywords.
         A music compilation titled "Best Songs" is still
         music — the audio codec and bitrate prove it.
      2. Slide-presentation: keyword-driven but only when
         not competing with strong list signals.
      3. List-edit: title/keyword-driven ranking content.
      4. Speech-heavy: any audio present that is not music,
         or recipe-flagged content.
      5. Mixed: fallback when no signal is strong enough.

    Args:
        job_id: UUID of the job being classified.
        audio: Audio check results from yt-dlp metadata.
        metadata: Metadata keyword signals.
        frame_count: Number of frames successfully sampled.
            A value of 0 indicates audio-only or sampling
            failure; does not block classification.
        video_duration_seconds: Duration in seconds from
            ffprobe via frame sampler, or job.duration_seconds
            as fallback.

    Returns:
        RouterDecision conforming to the Phase 1 contract.
    """
    decided_at = datetime.now(UTC)

    # Rule 1: MUSIC-HEAVY
    # Audio bitrate + codec evidence takes priority over
    # title keywords. A music compilation or ringtone with
    # "best" in the title is still music. The only guard is
    # a minimum duration to filter out test/stub files and
    # recipe content (cooking videos sometimes have high
    # audio bitrate but are clearly not music).
    if (
        audio.likely_music
        and not metadata.has_recipe_signal
        and video_duration_seconds >= MUSIC_MIN_DURATION_SECONDS
    ):
        return RouterDecision(
            job_id=job_id,
            primary_route="music-heavy",
            confidence=HIGH_CONFIDENCE,
            speech_density=0.2,
            ocr_density=0.1,
            decided_at=decided_at,
            routing_notes=(
                f"High audio bitrate music heuristic. "
                f"duration={video_duration_seconds:.1f}s "
                f"bitrate={audio.audio_bitrate_kbps}kbps"
            ),
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
            routing_notes=(
                f"List keywords: "
                f"{metadata.matched_keywords[:3]}"
            ),
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
