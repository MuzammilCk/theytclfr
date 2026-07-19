"""Tests for fusion/v3_groq_reasoner.py.

This module previously had zero test coverage. Covers:
- the entity contract fix (entity_type/mentioned_at/confidence,
  with defensive fallback to the old type/timestamps keys)
- the new retry-with-backoff behavior
- that auth failures (401/403) do not trigger a wasted retry
"""
import json
from unittest.mock import patch
from uuid import uuid4

from ytclfr.contracts.v3.evidence import EvidenceGraph
from ytclfr.core.config import Settings
from ytclfr.fusion.v3_groq_reasoner import (
    v3_reason_over_evidence,
    _parse_response,
    _build_prompt,
    GROQ_MAX_ATTEMPTS,
)


def _settings(api_key: str = "test-key") -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        groq_api_key=api_key,
        jwt_secret_key="test",
        groq_model="llama-3.3-70b-versatile",
        llm_request_timeout_seconds=30,
    )


def _graph(**overrides) -> EvidenceGraph:
    defaults = dict(
        job_id=uuid4(),
        segments=[],
        entities=[],
        total_segments=0,
        confidence=1.0,
    )
    defaults.update(overrides)
    return EvidenceGraph(**defaults)


class TestParseResponse:

    def test_parses_correct_field_names(self):
        raw = json.dumps({
            "dominant_subject": "Cooking",
            "summary": "A cooking video.",
            "entities": [
                {"name": "Olive Oil", "entity_type": "product",
                 "mentioned_at": [1.0, 5.0], "confidence": 0.88}
            ],
            "scene_boundaries": [0.0, 30.0],
        })
        result = _parse_response(raw)
        assert result.reasoning_used is True
        assert result.refined_entities[0]["name"] == "Olive Oil"
        assert result.refined_entities[0]["entity_type"] == "product"
        assert result.refined_entities[0]["mentioned_at"] == [1.0, 5.0]
        assert result.refined_entities[0]["confidence"] == 0.88

    def test_falls_back_to_legacy_key_names(self):
        """Defensive: if the model ignores the prompt and still replies
        with type/timestamps, we should still parse it correctly rather
        than silently dropping the entity."""
        raw = json.dumps({
            "dominant_subject": "Cooking",
            "summary": "A cooking video.",
            "entities": [
                {"name": "Olive Oil", "type": "product", "timestamps": [1.0]}
            ],
            "scene_boundaries": [0.0],
        })
        result = _parse_response(raw)
        assert result.refined_entities[0]["entity_type"] == "product"
        assert result.refined_entities[0]["mentioned_at"] == [1.0]
        assert result.refined_entities[0]["confidence"] == 0.7  # sensible default

    def test_invalid_entity_type_normalized_to_unknown(self):
        raw = json.dumps({
            "entities": [{"name": "Thing", "entity_type": "gadget"}],
        })
        result = _parse_response(raw)
        assert result.refined_entities[0]["entity_type"] == "unknown"

    def test_confidence_clamped_to_valid_range(self):
        raw = json.dumps({
            "entities": [{"name": "Thing", "entity_type": "topic", "confidence": 5.0}],
        })
        result = _parse_response(raw)
        assert result.refined_entities[0]["confidence"] == 1.0

    def test_output_is_directly_reconstructible_as_extracted_entity(self):
        """This is the exact crash this fix targets: Stage D reloads
        entities via ExtractedEntity.model_validate(e). The dicts we
        produce here must satisfy that contract directly."""
        from ytclfr.contracts.v3.evidence import ExtractedEntity

        raw = json.dumps({
            "entities": [
                {"name": "Olive Oil", "entity_type": "product", "mentioned_at": [1.0], "confidence": 0.9}
            ],
        })
        result = _parse_response(raw)
        # must not raise
        entity = ExtractedEntity.model_validate(result.refined_entities[0])
        assert entity.name == "Olive Oil"


class TestBuildPrompt:

    def test_includes_heuristic_entities_for_groq_to_refine(self):
        from ytclfr.contracts.v3.evidence import ExtractedEntity

        graph = _graph(entities=[
            ExtractedEntity(name="Python Tutorial", entity_type="unknown",
                             mentioned_at=[0.0], confidence=0.6)
        ])
        prompt = _build_prompt(graph)
        assert "Python Tutorial" in prompt
        assert "entities_extracted_by_heuristics" in prompt

    def test_countdown_structural_type_adds_explicit_list_instruction(self):
        graph = _graph(structural_video_type="countdown")
        prompt = _build_prompt(graph)
        assert "MULTIPLE distinct ranked items" in prompt

    def test_none_structural_type_has_no_list_instruction(self):
        graph = _graph(structural_video_type="none")
        prompt = _build_prompt(graph)
        assert "MULTIPLE distinct ranked items" not in prompt


class TestRetryBehavior:

    @patch("ytclfr.fusion.v3_groq_reasoner.time.sleep")
    @patch("ytclfr.fusion.v3_groq_reasoner._call_groq_api")
    def test_retries_once_then_succeeds(self, mock_call, mock_sleep):
        mock_call.side_effect = [
            TimeoutError("network blip"),
            json.dumps({"entities": [], "scene_boundaries": [0.0]}),
        ]
        result = v3_reason_over_evidence(_graph(), _settings())
        assert result.reasoning_used is True
        assert mock_call.call_count == 2
        mock_sleep.assert_called_once()

    @patch("ytclfr.fusion.v3_groq_reasoner.time.sleep")
    @patch("ytclfr.fusion.v3_groq_reasoner._call_groq_api")
    def test_exhausts_retries_and_degrades_gracefully(self, mock_call, mock_sleep):
        mock_call.side_effect = TimeoutError("still down")
        result = v3_reason_over_evidence(_graph(), _settings())
        assert result.reasoning_used is False
        assert mock_call.call_count == GROQ_MAX_ATTEMPTS

    @patch("ytclfr.fusion.v3_groq_reasoner.time.sleep")
    @patch("ytclfr.fusion.v3_groq_reasoner._call_groq_api")
    def test_auth_failure_does_not_retry(self, mock_call, mock_sleep):
        class FakeResponse:
            status_code = 401
        class FakeAuthError(Exception):
            response = FakeResponse()

        mock_call.side_effect = FakeAuthError("bad key")
        result = v3_reason_over_evidence(_graph(), _settings())
        assert result.reasoning_used is False
        assert mock_call.call_count == 1
        mock_sleep.assert_not_called()

    def test_missing_api_key_never_calls_groq(self):
        with patch("ytclfr.fusion.v3_groq_reasoner._call_groq_api") as mock_call:
            result = v3_reason_over_evidence(_graph(), _settings(api_key=""))
            assert result.reasoning_used is False
            mock_call.assert_not_called()
