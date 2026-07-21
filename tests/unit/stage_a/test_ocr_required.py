"""Regression tests for Stage A's OCR-dispatch decision.

Covers the bug where `ocr_required` was derived from a single fragile
per-frame Tesseract heuristic (`has_burned_in_text`) while ignoring
three other signals Stage A already computes in the same function: the
VLM's structural read, its overlay-text-density estimate, and a
zero-ML regex check on the title/description. A "Top 25 ..." video
whose raw heuristic came back False (e.g. due to an environment-
specific OCR quirk) would silently never get OCR dispatched by Stage B.
"""

from ytclfr.tasks.v3.stage_a_census import _compute_ocr_required


class TestComputeOcrRequired:
    def test_burned_in_text_alone_still_triggers_ocr(self) -> None:
        """Original behaviour is preserved: the raw heuristic alone
        is still sufficient, not just necessary."""
        assert _compute_ocr_required(
            has_burned_in_text=True,
            vlm_struct_type="none",
            overlay_density=0.0,
            title_has_ordinals=False,
            title_has_list_keywords=False,
        ) is True

    def test_title_ordinal_alone_triggers_ocr_even_if_heuristic_missed_it(
        self,
    ) -> None:
        """The reported bug: a 'Top 25 ...' title with the fragile
        per-frame heuristic coming back False must still dispatch OCR."""
        assert _compute_ocr_required(
            has_burned_in_text=False,
            vlm_struct_type="none",
            overlay_density=0.0,
            title_has_ordinals=True,
            title_has_list_keywords=False,
        ) is True

    def test_vlm_ranking_classification_alone_triggers_ocr(self) -> None:
        """'ranking' is a valid VLM category (see valid_types in
        vlm_structural_probe.py) and the single most likely read for a
        'Top N' video — it must not be silently ignored."""
        assert _compute_ocr_required(
            has_burned_in_text=False,
            vlm_struct_type="ranking",
            overlay_density=0.0,
            title_has_ordinals=False,
            title_has_list_keywords=False,
        ) is True

    def test_high_overlay_density_alone_triggers_ocr(self) -> None:
        assert _compute_ocr_required(
            has_burned_in_text=False,
            vlm_struct_type="none",
            overlay_density=0.5,
            title_has_ordinals=False,
            title_has_list_keywords=False,
        ) is True

    def test_overlay_density_just_under_threshold_does_not_trigger_alone(
        self,
    ) -> None:
        assert _compute_ocr_required(
            has_burned_in_text=False,
            vlm_struct_type="none",
            overlay_density=0.05,
            title_has_ordinals=False,
            title_has_list_keywords=False,
        ) is False

    def test_no_signals_present_does_not_require_ocr(self) -> None:
        """A genuinely silent/textless video (e.g. a talking-head vlog)
        should not be forced through OCR just because the gate got
        broadened — it should still be False when nothing suggests
        on-screen text."""
        assert _compute_ocr_required(
            has_burned_in_text=False,
            vlm_struct_type="none",
            overlay_density=0.0,
            title_has_ordinals=False,
            title_has_list_keywords=False,
        ) is False
