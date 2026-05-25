from ytclfr.taxonomy.intent_resolver import (
    resolve_by_rules,
    TaxonomyFallback,
    SUBJECT_KEYWORD_MAP,
    DEFAULT_CONFIDENCE,
)


class TestIntentResolver:

    def test_returns_taxonomy_fallback_type(self):
        """resolve_by_rules returns TaxonomyFallback."""
        result = resolve_by_rules("tutorial", True, False)
        assert isinstance(result, TaxonomyFallback)
        assert result.groq_used is False

    def test_tutorial_keyword_maps_to_education(self):
        """'tutorial' in subject → Education/Tutorial."""
        result = resolve_by_rules(
            dominant_subject="Python tutorial for beginners",
            has_speech=True, has_music=False,
        )
        assert result.parent_category == "Education"
        assert "Tutorial" in result.child_category

    def test_recipe_keyword_maps_to_food(self):
        """'recipe' in subject → Food/Recipe."""
        result = resolve_by_rules(
            dominant_subject="Italian pasta recipe",
            has_speech=True, has_music=False,
        )
        assert result.parent_category == "Food"

    def test_music_only_video_maps_to_music(self):
        """No speech + has_music → Music default."""
        result = resolve_by_rules(
            dominant_subject=None,
            has_speech=False, has_music=True,
        )
        assert result.parent_category == "Music"

    def test_no_signals_maps_to_other(self):
        """All false signals + no subject → Other."""
        result = resolve_by_rules(
            dominant_subject=None,
            has_speech=False, has_music=False,
        )
        assert result.parent_category == "Other"

    def test_fallback_always_has_notes(self):
        """fallback_notes is never empty — always documents the reason."""
        result = resolve_by_rules(None, False, False)
        assert len(result.fallback_notes) > 0

    def test_confidence_is_within_range(self):
        """Confidence from resolver is always 0.0–1.0."""
        for subject in [None, "tutorial", "recipe", "sports highlights"]:
            result = resolve_by_rules(subject, True, False)
            assert 0.0 <= result.confidence <= 1.0

    def test_all_keywords_map_to_valid_categories(self):
        """Every keyword in SUBJECT_KEYWORD_MAP maps to a valid parent."""
        valid = {
            "Education","Shopping","Sports","Music","Film",
            "Technology","Food","Health","News","Other",
        }
        for keyword, (parent, child, intent) in SUBJECT_KEYWORD_MAP.items():
            assert parent in valid, (
                f"keyword '{keyword}' maps to invalid parent '{parent}'"
            )
