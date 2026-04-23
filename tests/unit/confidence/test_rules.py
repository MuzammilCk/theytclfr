from ytclfr.confidence.rules import evaluate_branches
from ytclfr.confidence.scorer import SignalScore


def _score(val: float, has_data: bool = True) -> SignalScore:
    return SignalScore("test", val, "high", 1, has_data, "")


def test_low_asr_triggers_rescan():
    branch = evaluate_branches(
        asr=_score(0.3),
        ocr=_score(0.9),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    assert any(a.action == "rescan_asr" for a in branch.actions)
    assert branch.should_rescan is True


def test_low_ocr_triggers_rescan():
    branch = evaluate_branches(
        asr=_score(0.9),
        ocr=_score(0.2),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    assert any(a.action == "rescan_ocr" for a in branch.actions)
    assert branch.should_rescan is True


def test_low_asr_does_not_terminate_pipeline():
    branch = evaluate_branches(
        asr=_score(0.3),
        ocr=_score(0.9),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    actions = [a.action for a in branch.actions]
    assert "fail" not in actions
    assert "terminate" not in actions


def test_low_ocr_triggers_additional_frame_sampling():
    branch = evaluate_branches(
        asr=_score(0.9),
        ocr=_score(0.2),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    action = next(a for a in branch.actions if a.action == "rescan_ocr")
    assert "frame" in action.reason.lower()


def test_rescan_blocked_at_max_attempts():
    branch = evaluate_branches(
        asr=_score(0.3),
        ocr=_score(0.9),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=2,
        max_attempts=2,
    )
    assert not branch.should_rescan
    # Note: downgrade is only if score < DOWNGRADE_THRESHOLD.
    # If it's 0.3, it might just trust if no rule hits downgrade.
    # Ah, let's verify if downgrade triggers when below 0.2


def test_all_acceptable_returns_trust():
    branch = evaluate_branches(
        asr=_score(0.9),
        ocr=_score(0.9),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    assert branch.is_trusted is True
    assert len(branch.actions) == 1
    assert branch.actions[0].action == "trust"


def test_multiple_low_signals_multiple_actions():
    branch = evaluate_branches(
        asr=_score(0.3),
        ocr=_score(0.2),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    actions = {a.action for a in branch.actions}
    assert "rescan_asr" in actions
    assert "rescan_ocr" in actions


def test_downgrade_below_minimum():
    branch = evaluate_branches(
        asr=_score(0.1),
        ocr=_score(0.9),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=2,
        max_attempts=2,
    )
    assert branch.is_downgraded is True
    assert branch.actions[0].action == "downgrade"


def test_branch_decision_deterministic():
    branch1 = evaluate_branches(
        asr=_score(0.3),
        ocr=_score(0.2),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    branch2 = evaluate_branches(
        asr=_score(0.3),
        ocr=_score(0.2),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    assert branch1 == branch2


def test_fallback_branches_triggered_by_threshold_not_random():
    results = [
        evaluate_branches(
            asr=_score(0.1),
            ocr=_score(0.9),
            audio=_score(0.9),
            timeline=_score(0.9),
            attempt_count=2,
            max_attempts=2,
        )
        for _ in range(10)
    ]
    assert all(r == results[0] for r in results)


# ── Hardened tests from mutation testing audit ──────────────


def test_low_asr_no_rescan_when_has_data_false():
    """Mutation gap: has_data=False should block rescan_asr even with low score."""
    branch = evaluate_branches(
        asr=_score(0.3, has_data=False),
        ocr=_score(0.9),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    assert not any(a.action == "rescan_asr" for a in branch.actions)
    assert branch.is_trusted is True


def test_asr_at_exact_threshold_does_not_rescan():
    """Mutation gap: score exactly AT RESCAN_ASR_THRESHOLD should NOT trigger rescan."""
    from ytclfr.confidence.rules import RESCAN_ASR_THRESHOLD

    branch = evaluate_branches(
        asr=_score(RESCAN_ASR_THRESHOLD),
        ocr=_score(0.9),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    assert not any(a.action == "rescan_asr" for a in branch.actions)


def test_ocr_at_exact_threshold_does_not_rescan():
    """Mutation gap: score exactly AT RESCAN_OCR_THRESHOLD should NOT trigger rescan."""
    from ytclfr.confidence.rules import RESCAN_OCR_THRESHOLD

    branch = evaluate_branches(
        asr=_score(0.9),
        ocr=_score(RESCAN_OCR_THRESHOLD),
        audio=_score(0.9),
        timeline=_score(0.9),
        attempt_count=0,
        max_attempts=2,
    )
    assert not any(a.action == "rescan_ocr" for a in branch.actions)

