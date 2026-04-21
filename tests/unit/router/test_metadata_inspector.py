"""Tests for the metadata inspector module."""

from ytclfr.router.metadata_inspector import (
    MetadataSignals,
    inspect_metadata,
)


def test_detects_list_keywords_in_title():
    """Test list keyword detection — requires multi-word phrase."""
    meta = {
        "title": "Top 10 Best Movies of 2026",
        "description": "",
        "tags": [],
    }
    signals = inspect_metadata(meta)
    assert isinstance(signals, MetadataSignals)
    assert signals.has_list_signal is True


def test_detects_recipe_keywords():
    """Test recipe keyword detection across title and description."""
    meta = {
        "title": "How to make perfect pasta",
        "description": "cooking tutorial",
        "tags": ["recipe"],
    }
    signals = inspect_metadata(meta)
    assert signals.has_recipe_signal is True


def test_detects_slide_keywords():
    """Test slide/lecture keyword detection."""
    meta = {
        "title": "Introduction to Machine Learning",
        "description": "lecture slides course",
        "tags": [],
    }
    signals = inspect_metadata(meta)
    assert signals.has_slide_signal is True


def test_handles_empty_metadata():
    """Test safe defaults when metadata is empty."""
    signals = inspect_metadata({})
    assert signals.has_list_signal is False
    assert signals.has_recipe_signal is False
    assert signals.has_slide_signal is False
    assert signals.title == ""
    assert signals.tag_count == 0
    assert signals.matched_keywords == []


def test_no_false_positive_on_stop():
    """'stop' must not match 'top'. Regression for substring bug."""
    meta = {
        "title": "Stop and smell the roses",
        "description": "",
        "tags": [],
    }
    signals = inspect_metadata(meta)
    assert signals.has_list_signal is False


def test_no_false_positive_on_actually():
    """'actually' must not match 'all'. Regression for substring bug."""
    meta = {
        "title": "Actually the best song",
        "description": "I actually love this track",
        "tags": [],
    }
    signals = inspect_metadata(meta)
    # "best" is no longer a standalone keyword — needs phrase
    assert signals.has_list_signal is False


def test_no_false_positive_ringtone_title():
    """A ringtone title must not trigger list-edit routing.
    This is the primary regression test for the original bug.
    """
    meta = {
        "title": "Best iPhone Ringtone 2024 No Copyright",
        "description": "download free ringtone",
        "tags": ["ringtone", "iphone", "free"],
    }
    signals = inspect_metadata(meta)
    # "best" alone is not in LIST_KEYWORDS anymore —
    # only multi-word phrases like "best of" qualify.
    assert signals.has_list_signal is False


def test_detects_list_keyword_multi_word_phrase():
    """Multi-word list phrases must still be detected."""
    meta = {
        "title": "Best of 2024 — Top Ten Albums",
        "description": "",
        "tags": [],
    }
    signals = inspect_metadata(meta)
    assert signals.has_list_signal is True


def test_tags_included_in_keyword_search():
    """Tags must be included in normalized text for matching."""
    meta = {
        "title": "Pasta Night",
        "description": "",
        "tags": ["recipe", "cooking", "italian"],
    }
    signals = inspect_metadata(meta)
    assert signals.has_recipe_signal is True
    assert signals.tag_count == 3


def test_tutorial_does_not_set_recipe_signal():
    """'tutorial' was removed from RECIPE_KEYWORDS.
    It must only set has_slide_signal. Regression for
    double-keyword collision bug.
    """
    meta = {
        "title": "Photoshop tutorial for beginners",
        "description": "",
        "tags": [],
    }
    signals = inspect_metadata(meta)
    assert signals.has_slide_signal is True
    assert signals.has_recipe_signal is False


def test_slide_and_recipe_not_both_set_for_tutorial():
    """A tutorial title must not set both signals at once."""
    meta = {
        "title": "Advanced CSS tutorial",
        "description": "",
        "tags": [],
    }
    signals = inspect_metadata(meta)
    # One or neither — never both for a pure tutorial title
    assert not (
        signals.has_slide_signal and signals.has_recipe_signal
    )
