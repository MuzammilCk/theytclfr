import json
from unittest.mock import MagicMock, patch

from ytclfr.contracts.alignment import AlignedSegment
from ytclfr.contracts.evidence import ExtractedEntity
from ytclfr.fusion.groq_reasoner import (
    reason_over_evidence,
    _build_prompt,
    _parse_response,
    MAX_TRANSCRIPT_CHARS,
)
from ytclfr.core.config import Settings
from datetime import datetime, timezone


def _make_settings(api_key: str = "test-key") -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        groq_api_key=api_key,
        jwt_secret_key="test",
        groq_model="llama-3.3-70b-versatile",
        llm_request_timeout_seconds=30,
    )


def _make_segments(n: int = 3) -> list[AlignedSegment]:
    return [
        AlignedSegment(
            timestamp=float(i * 5),
            end_timestamp=float(i * 5 + 4),
            text=f"This is segment {i} about Python FastAPI",
            source="asr",
            confidence=0.9,
            original_segment_ids=[f"seg-{i}"],
        )
        for i in range(n)
    ]


class TestGroqReasoner:

    def test_empty_api_key_returns_failure_result(self):
        """Missing GROQ_API_KEY returns reasoning_used=False."""
        settings = _make_settings(api_key="")
        result = reason_over_evidence(
            segments=_make_segments(),
            entity_hints=[],
            settings=settings,
        )
        assert result.reasoning_used is False
        assert result.dominant_subject is None
        assert result.summary is None
        assert isinstance(result.scene_boundaries, list)

    @patch("ytclfr.fusion.groq_reasoner._call_groq_api")
    def test_successful_groq_call_parsed_correctly(self, mock_call):
        """Valid Groq JSON response is parsed into GroqReasoningResult."""
        mock_call.return_value = json.dumps({
            "dominant_subject": "Python FastAPI tutorial",
            "summary": "A tutorial about FastAPI.",
            "entities": [
                {"name": "FastAPI", "type": "topic",
                 "timestamps": [0.0, 5.0]},
            ],
            "scene_boundaries": [0.0, 10.0],
        })
        settings = _make_settings()
        result = reason_over_evidence(
            segments=_make_segments(),
            entity_hints=[],
            settings=settings,
        )
        assert result.reasoning_used is True
        assert result.dominant_subject == "Python FastAPI tutorial"
        assert len(result.refined_entities) == 1
        assert 0.0 in result.scene_boundaries

    @patch("ytclfr.fusion.groq_reasoner._call_groq_api")
    def test_groq_network_failure_degrades_gracefully(self, mock_call):
        """Network error returns reasoning_used=False without raising."""
        mock_call.side_effect = ConnectionError("Network timeout")
        settings = _make_settings()
        result = reason_over_evidence(
            segments=_make_segments(),
            entity_hints=[],
            settings=settings,
        )
        assert result.reasoning_used is False

    @patch("ytclfr.fusion.groq_reasoner._call_groq_api")
    def test_malformed_json_response_degrades_gracefully(self, mock_call):
        """Non-JSON Groq response returns reasoning_used=False."""
        mock_call.return_value = "not valid json {{{"
        settings = _make_settings()
        result = reason_over_evidence(
            segments=_make_segments(),
            entity_hints=[],
            settings=settings,
        )
        assert result.reasoning_used is False

    def test_build_prompt_respects_char_limit(self):
        """Prompt transcript is capped at MAX_TRANSCRIPT_CHARS."""
        long_segs = _make_segments(500)
        prompt = _build_prompt(long_segs, [], "none")
        # The transcript portion must not exceed the limit
        assert len(prompt) < MAX_TRANSCRIPT_CHARS + 2000  # prompt overhead

    def test_parse_response_always_has_scene_boundary(self):
        """Parsed response always contains at least [0.0] in boundaries."""
        raw = json.dumps({
            "dominant_subject": "x",
            "summary": "y",
            "entities": [],
            "scene_boundaries": [],
        })
        result = _parse_response(raw)
        assert 0.0 in result.scene_boundaries
