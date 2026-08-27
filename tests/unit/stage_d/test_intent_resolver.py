import pytest
from ytclfr.taxonomy.intent_resolver import resolve_by_rules

def test_resolve_by_rules_structural_override():
    result = resolve_by_rules(dominant_subject="Some random topic", has_speech=True, has_music=False, structural_video_type="ranking")
    
    assert result.parent_category == "Other"
    assert result.child_category == "Ranking"
    assert result.intent == "Consume structured content"
    assert any("Structural override applied" in note for note in result.fallback_notes)

def test_resolve_by_rules_no_structural_override():
    result = resolve_by_rules(dominant_subject="python coding", has_speech=True, has_music=False, structural_video_type="none")
    
    assert result.parent_category == "Technology"
    assert result.child_category == "Coding Tutorial"
    assert result.intent == "Write the code yourself"
    assert not any("Structural override applied" in note for note in result.fallback_notes)
