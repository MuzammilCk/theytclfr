import json
import pytest
from unittest.mock import patch
from ytclfr.taxonomy.mapper import (
    classify_taxonomy,
    _build_taxonomy_prompt,
    _parse_taxonomy_response,
    VALID_PARENT_CATEGORIES,
)
from ytclfr.core.config import Settings


def _make_settings(api_key: str = "test-key") -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        groq_api_key=api_key,
        jwt_secret_key="test",
        groq_model="llama-3.3-70b-versatile",
        llm_request_timeout_seconds=30,
    )


class TestTaxonomyMapper:

    def test_empty_api_key_returns_fallback(self):
        """Missing API key returns groq_used=False."""
        result = classify_taxonomy(
            dominant_subject="Python tutorial",
            groq_summary=None,
            entities=[],
            has_speech=True,
            has_music=False,
            settings=_make_settings(api_key=""),
        )
        assert result.groq_used is False
        assert result.parent_category in VALID_PARENT_CATEGORIES

    @patch("ytclfr.taxonomy.mapper._call_groq")
    def test_successful_groq_response_parsed(self, mock_call):
        """Valid Groq JSON is parsed into GroqTaxonomyResult."""
        mock_call.return_value = json.dumps({
            "parent_category": "Education",
            "child_category": "Coding Tutorial",
            "intent": "Learn to code",
            "confidence": 0.9,
        })
        result = classify_taxonomy(
            dominant_subject="Python programming",
            groq_summary="A Python coding tutorial",
            entities=[{"name": "Python", "type": "topic"}],
            has_speech=True,
            has_music=False,
            settings=_make_settings(),
        )
        assert result.groq_used is True
        assert result.parent_category == "Education"
        assert result.confidence == 0.9

    @patch("ytclfr.taxonomy.mapper._call_groq")
    def test_network_failure_returns_fallback(self, mock_call):
        """Network error returns groq_used=False without raising."""
        mock_call.side_effect = ConnectionError("timeout")
        result = classify_taxonomy(
            dominant_subject="sports highlights",
            groq_summary=None,
            entities=[],
            has_speech=True,
            has_music=False,
            settings=_make_settings(),
        )
        assert result.groq_used is False

    @patch("ytclfr.taxonomy.mapper._call_groq")
    def test_invalid_parent_category_normalized_to_other(
        self, mock_call
    ):
        """Unknown parent_category in Groq response → 'Other'."""
        mock_call.return_value = json.dumps({
            "parent_category": "NotACategory",
            "child_category": "Something",
            "intent": "Watch",
            "confidence": 0.6,
        })
        result = classify_taxonomy(
            dominant_subject=None, groq_summary=None,
            entities=[], has_speech=False, has_music=False,
            settings=_make_settings(),
        )
        assert result.parent_category == "Other"

    def test_build_prompt_contains_subject(self):
        """Prompt must contain the dominant_subject string."""
        prompt = _build_taxonomy_prompt(
            "Python tutorial", "A coding tutorial", []
        )
        assert "Python tutorial" in prompt

    def test_parse_response_confidence_clamped(self):
        """confidence > 1.0 in Groq response is clamped to 1.0."""
        raw = json.dumps({
            "parent_category": "Education",
            "child_category": "Tutorial",
            "intent": "Learn",
            "confidence": 2.5,
        })
        result = _parse_taxonomy_response(raw)
        assert result.confidence <= 1.0
