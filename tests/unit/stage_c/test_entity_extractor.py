import pytest

from ytclfr.contracts.alignment import AlignedSegment
from ytclfr.fusion.entity_extractor import (
    extract_entities_from_timeline,
    MIN_ENTITY_CHAR_LENGTH,
    MAX_ENTITIES_RETURNED,
)
from datetime import datetime, timezone


def _seg(timestamp: float, text: str, source: str = "asr") -> AlignedSegment:
    """Helper: build a minimal AlignedSegment."""
    return AlignedSegment(
        timestamp=timestamp,
        end_timestamp=timestamp + 2.0,
        text=text,
        source=source,
        confidence=0.9,
        original_segment_ids=[f"seg-{timestamp}"],
    )


class TestEntityExtractor:

    def test_empty_segments_returns_empty(self):
        """Empty segment list returns empty entity list."""
        result = extract_entities_from_timeline([])
        assert result == []

    def test_extracts_capitalized_phrases(self):
        """Title-Case phrases should be extracted as entities."""
        segs = [
            _seg(0.0, "Welcome to the Python Tutorial"),
            _seg(2.0, "We will use Python Tutorial today"),
        ]
        entities = extract_entities_from_timeline(segs)
        names = [e.name for e in entities]
        assert "Python Tutorial" in names

    def test_stop_words_not_extracted(self):
        """Common stop words must not become entities."""
        segs = [_seg(0.0, "But when The first is done")]
        entities = extract_entities_from_timeline(segs)
        stop_names = {"But", "When", "The", "First"}
        for e in entities:
            assert e.name not in stop_names

    def test_short_names_filtered(self):
        """Names shorter than MIN_ENTITY_CHAR_LENGTH are skipped."""
        segs = [_seg(0.0, "Hi As Be we go")]
        entities = extract_entities_from_timeline(segs)
        for e in entities:
            assert len(e.name) >= MIN_ENTITY_CHAR_LENGTH

    def test_confidence_increases_with_mentions(self):
        """More mentions → higher confidence."""
        segs = [
            _seg(float(i), "Python Tutorial is great")
            for i in range(10)
        ]
        entities = extract_entities_from_timeline(segs)
        for e in entities:
            if e.name == "Python Tutorial":
                assert e.confidence > 0.5

    def test_never_returns_more_than_max(self):
        """Result is capped at MAX_ENTITIES_RETURNED."""
        segs = []
        for i in range(100):
            segs.append(_seg(float(i), f"Entity{i:02d} Name{i:02d}"))
        result = extract_entities_from_timeline(segs)
        assert len(result) <= MAX_ENTITIES_RETURNED

    def test_never_raises_on_bad_input(self):
        """Malformed segments must not raise — returns []."""
        result = extract_entities_from_timeline(None)  # type: ignore
        assert isinstance(result, list)
