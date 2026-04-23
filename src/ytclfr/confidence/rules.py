from dataclasses import dataclass
from typing import Literal

from ytclfr.confidence.scorer import SignalScore

ActionType = Literal["trust", "rescan_ocr", "rescan_asr", "downgrade"]


@dataclass(frozen=True)
class ConfidenceAction:
    """A single action the pipeline should take."""

    action: ActionType
    reason: str
    target_signal: str | None  # which signal triggered this


@dataclass(frozen=True)
class BranchDecision:
    """The set of actions determined by confidence rules."""

    actions: list[ConfidenceAction]
    should_rescan: bool  # True if any action is rescan_*
    is_trusted: bool  # True if all signals are trusted
    is_downgraded: bool  # True if any signal is downgraded


# ── Thresholds — TUNABLE ──────────────────────
RESCAN_ASR_THRESHOLD: float = 0.40  # TUNABLE
RESCAN_OCR_THRESHOLD: float = 0.35  # TUNABLE
DOWNGRADE_THRESHOLD: float = 0.20  # TUNABLE
# ──────────────────────────────────────────────


def evaluate_branches(
    asr: SignalScore,
    ocr: SignalScore,
    audio: SignalScore,
    timeline: SignalScore,
    attempt_count: int,
    max_attempts: int,
) -> BranchDecision:
    actions = []

    # 1. Low ASR, rescan available
    if (
        asr.score < RESCAN_ASR_THRESHOLD
        and asr.has_data
        and attempt_count < max_attempts
    ):
        actions.append(
            ConfidenceAction(
                action="rescan_asr",
                reason="ASR confidence below threshold",
                target_signal="asr",
            )
        )

    # 2. Low OCR, rescan available
    if ocr.score < RESCAN_OCR_THRESHOLD and attempt_count < max_attempts:
        actions.append(
            ConfidenceAction(
                action="rescan_ocr",
                reason=(
                    "OCR confidence below threshold, "
                    "trigger additional frame sampling"
                ),
                target_signal="ocr",
            )
        )

    # 3. Below downgrade, no rescans left
    if attempt_count >= max_attempts:
        # if any signal score < DOWNGRADE_THRESHOLD
        if any(s.score < DOWNGRADE_THRESHOLD for s in [asr, ocr, audio, timeline]):
            actions.append(
                ConfidenceAction(
                    action="downgrade",
                    reason="Signal below minimum after max attempts",
                    target_signal=None,
                )
            )

    # 4. All signals acceptable
    if not actions:
        actions.append(
            ConfidenceAction(
                action="trust",
                reason="All signals within acceptable range",
                target_signal=None,
            )
        )

    should_rescan = any(a.action.startswith("rescan_") for a in actions)
    is_trusted = len(actions) == 1 and actions[0].action == "trust"
    is_downgraded = any(a.action == "downgrade" for a in actions)

    return BranchDecision(
        actions=actions,
        should_rescan=should_rescan,
        is_trusted=is_trusted,
        is_downgraded=is_downgraded,
    )
