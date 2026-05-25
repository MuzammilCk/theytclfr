"""Heuristic entity extraction from aligned timeline segments.

Pure function — no Celery, no DB, no network calls.
Extracts capitalized noun phrases from transcript text as
candidate entities with their timestamps.

Groq in groq_reasoner.py will refine entity types and
add semantic context. This module provides the initial
candidate set passed to Groq as context.
"""

import re

from ytclfr.contracts.alignment import AlignedSegment
from ytclfr.contracts.evidence import ExtractedEntity

# ── TUNABLE CONSTANTS ──────────────────────────────────────

# Regex: consecutive Title-Case words (2+ letters each)
CAPITALIZED_PHRASE: re.Pattern = re.compile(
    r'\b([A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,})*)\b'
)
# Regex: dollar price markers → indicates product context
PRICE_MARKER: re.Pattern = re.compile(r'\$\s*\d')

MIN_ENTITY_CHAR_LENGTH: int = 4     # skip short matches like "I" "A"
MAX_ENTITIES_RETURNED: int = 20     # cap output to keep prompt small
MIN_MENTIONS_FOR_ENTITY: int = 1    # must appear at least once
MAX_TIMESTAMPS_PER_ENTITY: int = 10 # cap stored timestamps
CONFIDENCE_SCALE_DENOMINATOR: float = 5.0  # 5 mentions = 1.0


# Common title-case words that are NOT entities
_STOP_NAMES: frozenset[str] = frozenset({
    "The", "This", "That", "These", "Those",
    "When", "Where", "What", "Which", "While",
    "But", "And", "For", "With", "From",
    "Here", "There", "Then", "Also", "Now",
    "Just", "Even", "Still", "Already",
    "First", "Second", "Third", "Next", "Last",
})


def extract_entities_from_timeline(
    segments: list[AlignedSegment],
) -> list[ExtractedEntity]:
    """Extract named entity candidates from aligned segments.

    Uses regex heuristics to find Title-Case noun phrases.
    Returns at most MAX_ENTITIES_RETURNED entities sorted
    by descending confidence.

    Args:
        segments: AlignedSegment list from align().

    Returns:
        List of ExtractedEntity objects with heuristic types.
        Always returns a list — never raises.
    """
    if not segments:
        return []

    try:
        return _extract_entities(segments)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Entity extraction failed: %s", exc
        )
        return []


def _extract_entities(
    segments: list[AlignedSegment],
) -> list[ExtractedEntity]:
    """Inner extraction logic. Called only from extract_entities_from_timeline."""
    from collections import defaultdict

    entity_timestamps: dict[str, list[float]] = defaultdict(list)

    for seg in segments:
        text = seg.text
        # Check price context (optional, can be used for future heuristics)
        if PRICE_MARKER.search(text):
            pass
        for match in CAPITALIZED_PHRASE.finditer(text):
            name = match.group(1).strip()
            if len(name) < MIN_ENTITY_CHAR_LENGTH:
                continue
            # Skip pure stop-word matches
            if name.lower() in {s.lower() for s in _STOP_NAMES}:
                continue
            entity_timestamps[name].append(seg.timestamp)

    entities: list[ExtractedEntity] = []
    for name, timestamps in entity_timestamps.items():
        if len(timestamps) < MIN_MENTIONS_FOR_ENTITY:
            continue
        unique_ts = sorted(set(timestamps))[:MAX_TIMESTAMPS_PER_ENTITY]
        confidence = min(
            len(unique_ts) / CONFIDENCE_SCALE_DENOMINATOR, 1.0
        )
        entity_type = _infer_type(name)
        entities.append(
            ExtractedEntity(
                name=name,
                entity_type=entity_type,
                mentioned_at=unique_ts,
                confidence=round(confidence, 3),
            )
        )

    return sorted(
        entities, key=lambda e: -e.confidence
    )[:MAX_ENTITIES_RETURNED]


def _infer_type(name: str) -> str:
    """Infer entity type from name pattern.

    Intentionally conservative — Groq provides final types.
    """
    words = name.split()
    # All-caps short tokens → likely a topic/acronym
    if name.isupper() and len(name) <= 6:
        return "topic"
    # Single word → topic (too ambiguous for product/person/place)
    if len(words) == 1:
        return "topic"
    # Two+ title-case words → unknown (Groq will classify)
    return "unknown"
