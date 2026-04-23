from dataclasses import dataclass
from typing import Any

from ytclfr.confidence.policy import (
    RescanPolicy,
    UncertaintyMarker,
    build_rescan_policy,
    mark_uncertain_outputs,
)
from ytclfr.confidence.rules import BranchDecision, evaluate_branches
from ytclfr.confidence.scorer import (
    AggregateScore,
    compute_aggregate_score,
    score_asr,
    score_audio,
    score_ocr,
    score_timeline,
)


@dataclass(frozen=True)
class ConfidenceVerdict:
    """Final verdict from the Confidence Controller."""

    aggregate_score: AggregateScore
    branch_decision: BranchDecision
    rescan_policy: RescanPolicy
    uncertainty_markers: list[UncertaintyMarker]
    should_proceed: bool  # True = continue pipeline, False = rescan needed
    is_confident: bool  # True = all trusted, no uncertainty
    verdict_notes: str  # human-readable summary


def evaluate(
    extractor_results: list[dict[str, Any]],
    aligned_timeline_dict: dict[str, Any],
    current_attempt: int = 0,
) -> ConfidenceVerdict:
    asr = score_asr(extractor_results)
    ocr = score_ocr(extractor_results)
    audio = score_audio(extractor_results)
    timeline = score_timeline(aligned_timeline_dict)

    aggregate = compute_aggregate_score(asr, ocr, audio, timeline)
    policy = build_rescan_policy(current_attempt)
    branch = evaluate_branches(
        asr=asr,
        ocr=ocr,
        audio=audio,
        timeline=timeline,
        attempt_count=current_attempt,
        max_attempts=policy.max_attempts,
    )
    markers = mark_uncertain_outputs(aggregate.signals)

    should_proceed = not branch.should_rescan
    is_confident = branch.is_trusted and not aggregate.is_uncertain

    notes_parts = []
    if is_confident:
        notes_parts.append("All signals confident.")
    else:
        if aggregate.is_uncertain:
            notes_parts.append("Some signals uncertain.")
        if branch.should_rescan:
            notes_parts.append("Rescan triggered.")
        if branch.is_downgraded:
            notes_parts.append("Downgraded due to max attempts.")

    verdict_notes = " ".join(notes_parts) if notes_parts else "Evaluation complete."

    return ConfidenceVerdict(
        aggregate_score=aggregate,
        branch_decision=branch,
        rescan_policy=policy,
        uncertainty_markers=markers,
        should_proceed=should_proceed,
        is_confident=is_confident,
        verdict_notes=verdict_notes,
    )
