from dataclasses import dataclass
from typing import Any

# ── Thresholds — TUNABLE ──────────────────────
ASR_HIGH_CONFIDENCE: float = 0.75  # TUNABLE
ASR_LOW_CONFIDENCE: float = 0.40  # TUNABLE
OCR_HIGH_CONFIDENCE: float = 0.70  # TUNABLE
OCR_LOW_CONFIDENCE: float = 0.35  # TUNABLE
AUDIO_HIGH_CONFIDENCE: float = 0.80  # TUNABLE
AUDIO_LOW_CONFIDENCE: float = 0.50  # TUNABLE
TIMELINE_MIN_SEGMENTS: int = 1  # TUNABLE
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class SignalScore:
    """Confidence score for a single signal type."""

    signal_type: str  # "asr", "ocr", "audio", "timeline"
    score: float  # 0.0–1.0
    level: str  # "high", "medium", "low"
    segment_count: int  # number of segments contributing
    has_data: bool  # True if extractor produced data
    notes: str  # human-readable explanation


@dataclass(frozen=True)
class AggregateScore:
    """Combined confidence across all signals."""

    overall: float  # 0.0–1.0 weighted average
    signals: list[SignalScore]
    is_uncertain: bool  # True if any signal is "low"


def score_asr(
    extractor_results: list[dict[str, Any]],
) -> SignalScore:
    """Score the ASR extraction results."""
    for result in extractor_results:
        if result.get("extractor_type") == "asr":
            if result.get("error") is not None:
                return SignalScore(
                    signal_type="asr",
                    score=0.0,
                    level="low",
                    segment_count=0,
                    has_data=False,
                    notes="ASR extraction failed or missing",
                )
            segments = result.get("segments", [])
            if not segments:
                return SignalScore(
                    signal_type="asr",
                    score=0.0,
                    level="low",
                    segment_count=0,
                    has_data=False,
                    notes="No ASR segments found",
                )
            avg_score = sum(seg.get("confidence", 0.0) for seg in segments) / len(
                segments
            )

            level = "low"
            if avg_score >= ASR_HIGH_CONFIDENCE:
                level = "high"
            elif avg_score >= ASR_LOW_CONFIDENCE:
                level = "medium"

            return SignalScore(
                signal_type="asr",
                score=avg_score,
                level=level,
                segment_count=len(segments),
                has_data=True,
                notes=f"ASR average confidence: {avg_score:.2f}",
            )

    return SignalScore(
        signal_type="asr",
        score=0.0,
        level="low",
        segment_count=0,
        has_data=False,
        notes="ASR extraction failed or missing",
    )


def score_ocr(
    extractor_results: list[dict[str, Any]],
) -> SignalScore:
    """Score the OCR extraction results."""
    for result in extractor_results:
        if result.get("extractor_type") == "ocr":
            if result.get("error") is not None:
                return SignalScore(
                    signal_type="ocr",
                    score=0.0,
                    level="low",
                    segment_count=0,
                    has_data=False,
                    notes="OCR extraction failed or missing",
                )
            segments = result.get("segments", [])
            if not segments:
                return SignalScore(
                    signal_type="ocr",
                    score=0.0,
                    level="low",
                    segment_count=0,
                    has_data=False,
                    notes="No OCR segments found",
                )
            avg_score = sum(seg.get("confidence", 0.0) for seg in segments) / len(
                segments
            )

            level = "low"
            if avg_score >= OCR_HIGH_CONFIDENCE:
                level = "high"
            elif avg_score >= OCR_LOW_CONFIDENCE:
                level = "medium"

            return SignalScore(
                signal_type="ocr",
                score=avg_score,
                level=level,
                segment_count=len(segments),
                has_data=True,
                notes=f"OCR average confidence: {avg_score:.2f}",
            )

    return SignalScore(
        signal_type="ocr",
        score=0.0,
        level="low",
        segment_count=0,
        has_data=False,
        notes="OCR extraction failed or missing",
    )


def score_audio(
    extractor_results: list[dict[str, Any]],
) -> SignalScore:
    """Score the audio classification results."""
    for result in extractor_results:
        if result.get("extractor_type") == "audio":
            if result.get("error") is not None:
                return SignalScore(
                    signal_type="audio",
                    score=0.0,
                    level="low",
                    segment_count=0,
                    has_data=False,
                    notes="Audio classification failed or missing",
                )
            segments = result.get("segments", [])
            if not segments:
                return SignalScore(
                    signal_type="audio",
                    score=0.0,
                    level="low",
                    segment_count=0,
                    has_data=False,
                    notes="No audio segments found",
                )
            avg_score = sum(seg.get("confidence", 0.0) for seg in segments) / len(
                segments
            )

            has_no_audio = any(seg.get("label") == "no_audio" for seg in segments)
            if has_no_audio:
                return SignalScore(
                    signal_type="audio",
                    score=0.0,
                    level="low",
                    segment_count=len(segments),
                    has_data=True,
                    notes="Audio labeled as no_audio",
                )

            level = "low"
            if avg_score >= AUDIO_HIGH_CONFIDENCE:
                level = "high"
            elif avg_score >= AUDIO_LOW_CONFIDENCE:
                level = "medium"

            return SignalScore(
                signal_type="audio",
                score=avg_score,
                level=level,
                segment_count=len(segments),
                has_data=True,
                notes=f"Audio average confidence: {avg_score:.2f}",
            )

    return SignalScore(
        signal_type="audio",
        score=0.0,
        level="low",
        segment_count=0,
        has_data=False,
        notes="Audio classification failed or missing",
    )


def score_timeline(
    aligned_timeline_dict: dict[str, Any],
) -> SignalScore:
    """Score the aligned timeline."""
    total_segments = aligned_timeline_dict.get("total_segments", 0)
    has_gaps = aligned_timeline_dict.get("has_gaps", False)
    segments = aligned_timeline_dict.get("segments", [])

    if total_segments == 0:
        return SignalScore(
            signal_type="timeline",
            score=0.0,
            level="low",
            segment_count=0,
            has_data=False,
            notes="Empty timeline",
        )

    if total_segments < TIMELINE_MIN_SEGMENTS:
        return SignalScore(
            signal_type="timeline",
            score=0.3,
            level="low",
            segment_count=total_segments,
            has_data=True,
            notes="Timeline has too few segments",
        )

    avg_score = 0.0
    if segments:
        avg_score = sum(seg.get("confidence", 0.0) for seg in segments) / len(segments)

    if has_gaps:
        avg_score = max(0.0, avg_score - 0.15)

    level = "low"
    if avg_score >= 0.75:
        level = "high"
    elif avg_score >= 0.40:
        level = "medium"

    return SignalScore(
        signal_type="timeline",
        score=avg_score,
        level=level,
        segment_count=total_segments,
        has_data=True,
        notes=f"Timeline avg confidence: {avg_score:.2f}"
        + (" (reduced due to gaps)" if has_gaps else ""),
    )


# Signal weights — TUNABLE
ASR_WEIGHT: float = 0.45  # TUNABLE
OCR_WEIGHT: float = 0.30  # TUNABLE
AUDIO_WEIGHT: float = 0.10  # TUNABLE
TIMELINE_WEIGHT: float = 0.15  # TUNABLE


def compute_aggregate_score(
    asr: SignalScore,
    ocr: SignalScore,
    audio: SignalScore,
    timeline: SignalScore,
) -> AggregateScore:
    overall = (
        asr.score * ASR_WEIGHT
        + ocr.score * OCR_WEIGHT
        + audio.score * AUDIO_WEIGHT
        + timeline.score * TIMELINE_WEIGHT
    )
    overall = max(0.0, min(1.0, overall))
    signals = [asr, ocr, audio, timeline]
    is_uncertain = any(s.level == "low" for s in signals)

    return AggregateScore(
        overall=overall,
        signals=signals,
        is_uncertain=is_uncertain,
    )
