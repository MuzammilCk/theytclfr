"""Inspect video title, description, and tags for content type signals."""

from dataclasses import dataclass, field
from typing import Any

# Keyword sets — module-level constants
# These are tunable. Mark with TUNABLE comment.

LIST_KEYWORDS: frozenset[str] = frozenset({  # TUNABLE
    "top", "best", "ranking", "ranked", "list",
    "every", "all", "worst", "most", "least",
    "ultimate", "definitive", "complete",
})

RECIPE_KEYWORDS: frozenset[str] = frozenset({  # TUNABLE
    "recipe", "how to make", "cook", "cooking",
    "bake", "baking", "ingredients", "tutorial",
    "diy", "step by step", "how to",
})

SLIDE_KEYWORDS: frozenset[str] = frozenset({  # TUNABLE
    "lecture", "presentation", "slides", "course",
    "class", "lesson", "tutorial", "explained",
    "introduction to", "overview of",
})


@dataclass
class MetadataSignals:
    """Signals extracted from video metadata inspection."""

    title: str
    has_list_signal: bool
    has_recipe_signal: bool
    has_slide_signal: bool
    has_description: bool
    tag_count: int
    matched_keywords: list[str] = field(default_factory=list)


def inspect_metadata(
    metadata_raw: dict[str, Any],
) -> MetadataSignals:
    """Inspect video metadata for content type keyword signals.

    Checks title, description, and tags against keyword sets
    for list, recipe, and slide/lecture content patterns.

    Pure function — no I/O.

    Args:
        metadata_raw: Raw metadata dictionary.

    Returns:
        MetadataSignals with detected content signals.
    """
    title = metadata_raw.get("title", "") or ""
    description = metadata_raw.get("description", "") or ""
    tags = metadata_raw.get("tags", []) or []
    if not isinstance(tags, list):
        tags = []

    # Normalize: combine title + description, lowercase
    normalized = (title + " " + description).lower()

    # Check each keyword set
    matched_keywords: list[str] = []

    has_list_signal = False
    for kw in LIST_KEYWORDS:
        if kw in normalized:
            has_list_signal = True
            matched_keywords.append(kw)

    has_recipe_signal = False
    for kw in RECIPE_KEYWORDS:
        if kw in normalized:
            has_recipe_signal = True
            matched_keywords.append(kw)

    has_slide_signal = False
    for kw in SLIDE_KEYWORDS:
        if kw in normalized:
            has_slide_signal = True
            matched_keywords.append(kw)

    return MetadataSignals(
        title=title,
        has_list_signal=has_list_signal,
        has_recipe_signal=has_recipe_signal,
        has_slide_signal=has_slide_signal,
        has_description=bool(description.strip()),
        tag_count=len(tags),
        matched_keywords=matched_keywords,
    )
