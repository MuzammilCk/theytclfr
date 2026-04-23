from dataclasses import dataclass

from ytclfr.confidence.scorer import SignalScore

# ── Policy constants — TUNABLE ────────────────
MAX_RESCAN_ATTEMPTS: int = 2  # TUNABLE
OCR_RESCAN_EXTRA_FRAMES: int = 3  # TUNABLE — additional frames per rescan
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class RescanPolicy:
    """Rescan policy state for a job."""

    max_attempts: int
    current_attempt: int
    can_rescan: bool
    ocr_extra_frames: int  # how many extra frames to sample


@dataclass(frozen=True)
class UncertaintyMarker:
    """Marks uncertain output explicitly."""

    signal_type: str
    original_score: float
    is_uncertain: bool
    reason: str


def build_rescan_policy(
    current_attempt: int = 0,
) -> RescanPolicy:
    can_rescan = current_attempt < MAX_RESCAN_ATTEMPTS
    ocr_extra_frames = OCR_RESCAN_EXTRA_FRAMES * (current_attempt + 1)

    return RescanPolicy(
        max_attempts=MAX_RESCAN_ATTEMPTS,
        current_attempt=current_attempt,
        can_rescan=can_rescan,
        ocr_extra_frames=ocr_extra_frames,
    )


def mark_uncertain_outputs(
    signals: list[SignalScore],
) -> list[UncertaintyMarker]:
    markers = []
    for signal in signals:
        if signal.level == "low":
            markers.append(
                UncertaintyMarker(
                    signal_type=signal.signal_type,
                    original_score=signal.score,
                    is_uncertain=True,
                    reason=f"Signal level is low. Notes: {signal.notes}",
                )
            )
    return markers
