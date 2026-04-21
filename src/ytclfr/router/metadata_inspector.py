import re
from dataclasses import dataclass, field
from typing import Any

# Keyword sets — module-level constants
# These are tunable. Marked with # TUNABLE comment.
# All matching uses word boundaries (re.search with \b).
# Single-letter or ambiguous short tokens have been
# removed to prevent substring false positives
# (e.g. "all" matching "actually", "top" matching "stop").

LIST_KEYWORDS: frozenset[str] = frozenset({  # TUNABLE
    "top 10", "top 5", "top 3", "top ten", "top five",
    "best of", "ranking", "ranked", "ranked list",
    "worst of", "most popular", "least popular",
    "ultimate list", "definitive list", "complete list",
    "every single", "all time best", "all time worst",
})

# Minimum number of LIST_KEYWORDS that must match for
# has_list_signal to be True. Prevents single-word
# title coincidences from triggering list routing.
LIST_KEYWORD_MIN_MATCHES: int = 1  # TUNABLE

RECIPE_KEYWORDS: frozenset[str] = frozenset({  # TUNABLE
    "recipe", "how to make", "cook", "cooking",
    "bake", "baking", "ingredients", "diy",
    "step by step", "how to",
})
# NOTE: "tutorial" was removed from RECIPE_KEYWORDS.
# It exists only in SLIDE_KEYWORDS. Reason: tutorial
# content is structured educational material, not culinary.
# Keeping it in both sets caused double-flagging and
# unpredictable rule priority. See DR-12.

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


def _keyword_matches(
    text: str, keywords: frozenset[str]
) -> list[str]:
    """Return list of keywords found in text using word
    boundary matching. Multi-word phrases match as a
    substring unit. Single words match only at word
    boundaries to prevent partial matches like 'stop'
    triggering 'top'.
    """
    found: list[str] = []
    for kw in keywords:
        # Word boundaries work correctly for multi-word
        # phrases — \b anchors the first and last character
        # of the entire phrase.
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, text):
            found.append(kw)
    return found


def inspect_metadata(
    metadata_raw: dict[str, Any],
) -> MetadataSignals:
    """Inspect video metadata for content type keyword signals.

    Checks title, description, AND tags against keyword sets
    for list, recipe, and slide/lecture content patterns.
    Uses word-boundary regex matching to prevent substring
    false positives.

    Pure function — no I/O.

    Args:
        metadata_raw: yt-dlp info dict from job.metadata_raw.

    Returns:
        MetadataSignals with detected content signals.
    """
    title = metadata_raw.get("title", "") or ""
    description = metadata_raw.get("description", "") or ""
    tags = metadata_raw.get("tags", []) or []
    if not isinstance(tags, list):
        tags = []

    # Build normalized search text from title + description
    # + all tags. Tags are joined with spaces so word
    # boundaries work correctly across tag values.
    tags_text = " ".join(str(t) for t in tags if t)
    normalized = (
        title + " " + description + " " + tags_text
    ).lower()

    # Match each keyword set
    list_matches = _keyword_matches(normalized, LIST_KEYWORDS)
    recipe_matches = _keyword_matches(
        normalized, RECIPE_KEYWORDS
    )
    slide_matches = _keyword_matches(
        normalized, SLIDE_KEYWORDS
    )

    matched_keywords: list[str] = (
        list_matches + recipe_matches + slide_matches
    )

    has_list_signal = (
        len(list_matches) >= LIST_KEYWORD_MIN_MATCHES
    )
    has_recipe_signal = len(recipe_matches) > 0
    has_slide_signal = len(slide_matches) > 0

    return MetadataSignals(
        title=title,
        has_list_signal=has_list_signal,
        has_recipe_signal=has_recipe_signal,
        has_slide_signal=has_slide_signal,
        has_description=bool(description.strip()),
        tag_count=len(tags),
        matched_keywords=matched_keywords,
    )
