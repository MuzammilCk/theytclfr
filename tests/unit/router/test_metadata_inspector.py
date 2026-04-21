"""Tests for the metadata inspector module."""

from ytclfr.router.metadata_inspector import MetadataSignals, inspect_metadata


def test_detects_list_keywords_in_title():
    """Test list keyword detection in title."""
    meta = {
        "title": "Top 10 Best Movies of 2026",
        "description": "",
        "tags": [],
    }
    signals = inspect_metadata(meta)
    assert isinstance(signals, MetadataSignals)
    assert signals.has_list_signal is True
    assert "top" in signals.matched_keywords
    assert "best" in signals.matched_keywords


def test_detects_recipe_keywords():
    """Test recipe keyword detection across title and description."""
    meta = {
        "title": "How to make perfect pasta",
        "description": "cooking tutorial",
        "tags": ["recipe"],
    }
    signals = inspect_metadata(meta)
    assert signals.has_recipe_signal is True
    assert any(
        kw in signals.matched_keywords
        for kw in ["how to make", "cooking", "tutorial"]
    )


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
