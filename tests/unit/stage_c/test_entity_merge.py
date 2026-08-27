"""Regression tests for Stage C's entity merge logic.

Covers the bug where Groq's refined entity list *replaced* the
heuristic baseline outright. On a ranked-list video with OCR-derived
(sometimes noisy) candidates, Groq could legitimately return valid
JSON with far fewer entities than the heuristic pass already found —
e.g. 16 OCR segments in, 4 refined entities out — and nothing caught
the regression: the classifier could still correctly recognize "this
is a ranked movie list" from dominant_subject/summary while the
`items` list silently lost most of its content.
"""

from ytclfr.contracts.v3.evidence import ExtractedEntity
from ytclfr.tasks.v3.stage_c_fusion import _merge_entities, _normalize_entity_name


def _heuristic(name: str, confidence: float = 0.6) -> ExtractedEntity:
    return ExtractedEntity(
        name=name, entity_type="unknown", mentioned_at=[1.0], confidence=confidence,
    )


class TestNormalizeEntityName:
    def test_case_and_punctuation_insensitive(self) -> None:
        assert _normalize_entity_name("The Godfather") == _normalize_entity_name(
            "THE GODFATHER"
        )

    def test_different_titles_do_not_collide(self) -> None:
        assert _normalize_entity_name("Dune") != _normalize_entity_name("Dune: Part Two")


class TestMergeEntities:
    def test_groq_under_delivery_does_not_shrink_the_list(self) -> None:
        """The exact reported bug: 16 heuristic candidates in, Groq
        keeps only a handful — the merged result must still contain
        everything Groq dropped."""
        heuristic = [_heuristic(f"Movie {i}") for i in range(16)]
        groq_entities = [
            {"name": "Movie 0", "entity_type": "topic", "mentioned_at": [1.0], "confidence": 0.9},
            {"name": "Movie 1", "entity_type": "topic", "mentioned_at": [1.0], "confidence": 0.9},
        ]
        merged = _merge_entities(groq_entities, heuristic)
        assert len(merged) == 16
        names = {m["name"] for m in merged}
        assert names == {f"Movie {i}" for i in range(16)}

    def test_groq_entity_wins_over_heuristic_duplicate(self) -> None:
        """When Groq recognizes the same entity (possibly re-cased/
        re-typed), keep Groq's version rather than duplicating it."""
        heuristic = [_heuristic("THE GODFATHER")]
        groq_entities = [
            {"name": "The Godfather", "entity_type": "topic", "mentioned_at": [1.0], "confidence": 0.95},
        ]
        merged = _merge_entities(groq_entities, heuristic)
        assert len(merged) == 1
        assert merged[0]["name"] == "The Godfather"
        assert merged[0]["confidence"] == 0.95

    def test_empty_groq_entities_falls_back_to_full_heuristic_list(self) -> None:
        heuristic = [_heuristic("Movie A"), _heuristic("Movie B")]
        merged = _merge_entities([], heuristic)
        assert {m["name"] for m in merged} == {"Movie A", "Movie B"}

    def test_no_heuristic_entities_returns_groq_entities_unchanged(self) -> None:
        groq_entities = [
            {"name": "Movie A", "entity_type": "topic", "mentioned_at": [1.0], "confidence": 0.9},
        ]
        merged = _merge_entities(groq_entities, [])
        assert merged == groq_entities
