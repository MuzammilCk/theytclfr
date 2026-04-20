"""Schema validation tests for all Phase 1 data contracts.

Each test loads a golden JSON fixture and validates it against
its Pydantic model. Invalid payloads must raise ValidationError.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ytclfr.contracts.alignment import AlignedTimeline
from ytclfr.contracts.auth import AuthToken, JWTPayload
from ytclfr.contracts.events import VideoIngestedEvent
from ytclfr.contracts.extractor import ExtractorResult
from ytclfr.contracts.output import FinalOutput
from ytclfr.contracts.router import RouterDecision

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


def _load_fixture(name: str) -> dict[str, object]:
    """Load a JSON fixture file by name."""
    fixture_path = FIXTURES_DIR / name
    with fixture_path.open("r", encoding="utf-8") as f:
        data: dict[str, object] = json.load(f)
    return data


# ── VideoIngestedEvent ────────────────────────────────


class TestVideoIngestedEvent:
    """Tests for VideoIngestedEvent schema validation."""

    def test_valid_fixture(self) -> None:
        data = _load_fixture("video_ingested_event.json")
        event = VideoIngestedEvent.model_validate(data)
        assert str(event.job_id) == data["job_id"]
        assert event.youtube_url == data["youtube_url"]
        assert event.video_title == data["video_title"]
        assert event.channel_name == data["channel_name"]
        assert event.duration_seconds == data["duration_seconds"]
        assert event.local_media_path == data["local_media_path"]

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            VideoIngestedEvent.model_validate(
                {
                    "job_id": "not-a-uuid",
                    "youtube_url": 12345,
                }
            )


# ── RouterDecision ────────────────────────────────────


class TestRouterDecision:
    """Tests for RouterDecision schema validation."""

    def test_valid_fixture(self) -> None:
        data = _load_fixture("router_decision.json")
        decision = RouterDecision.model_validate(data)
        assert str(decision.job_id) == data["job_id"]
        assert decision.primary_route == data["primary_route"]
        assert decision.confidence == data["confidence"]
        assert decision.speech_density == data["speech_density"]
        assert decision.ocr_density == data["ocr_density"]

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            RouterDecision.model_validate(
                {
                    "job_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                    "primary_route": "invalid-route-type",
                    "confidence": 2.0,
                    "speech_density": 0.5,
                    "ocr_density": 0.5,
                    "decided_at": "2026-04-20T06:31:00Z",
                }
            )


# ── ExtractorResult (ASR) ─────────────────────────────


class TestExtractorResultASR:
    """Tests for ExtractorResult schema with ASR segments."""

    def test_valid_fixture(self) -> None:
        data = _load_fixture("extractor_result_asr.json")
        result = ExtractorResult.model_validate(data)
        assert str(result.job_id) == data["job_id"]
        assert result.extractor_type == "asr"
        assert len(result.segments) == 3
        assert result.error is None

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            ExtractorResult.model_validate(
                {
                    "job_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                    "extractor_type": "invalid_type",
                    "segments": [],
                    "total_duration_seconds": -1.0,
                    "extracted_at": "2026-04-20T06:35:00Z",
                }
            )


# ── ExtractorResult (OCR) ─────────────────────────────


class TestExtractorResultOCR:
    """Tests for ExtractorResult schema with OCR segments."""

    def test_valid_fixture(self) -> None:
        data = _load_fixture("extractor_result_ocr.json")
        result = ExtractorResult.model_validate(data)
        assert str(result.job_id) == data["job_id"]
        assert result.extractor_type == "ocr"
        assert len(result.segments) == 3
        assert result.error is None

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            ExtractorResult.model_validate(
                {
                    "job_id": "not-valid",
                    "extractor_type": "ocr",
                    "segments": "not-a-list",
                    "total_duration_seconds": 100.0,
                    "extracted_at": "2026-04-20T06:36:00Z",
                }
            )


# ── AlignedTimeline ───────────────────────────────────


class TestAlignedTimeline:
    """Tests for AlignedTimeline schema validation."""

    def test_valid_fixture(self) -> None:
        data = _load_fixture("aligned_segment.json")
        timeline = AlignedTimeline.model_validate(data)
        assert str(timeline.job_id) == data["job_id"]
        assert timeline.total_segments == 4
        assert len(timeline.segments) == 4
        assert timeline.has_gaps is False
        sources = {seg.source for seg in timeline.segments}
        assert sources == {"asr", "ocr", "merged"}

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            AlignedTimeline.model_validate(
                {
                    "job_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                    "segments": [
                        {
                            "timestamp": -5.0,
                            "source": "invalid_source",
                            "text": "bad",
                            "confidence": 1.5,
                            "original_segment_ids": [],
                        }
                    ],
                    "total_segments": 1,
                    "has_gaps": False,
                    "aligned_at": "2026-04-20T06:38:00Z",
                }
            )


# ── FinalOutput ───────────────────────────────────────


class TestFinalOutput:
    """Tests for FinalOutput schema validation."""

    def test_valid_fixture(self) -> None:
        data = _load_fixture("final_output.json")
        output = FinalOutput.model_validate(data)
        assert str(output.job_id) == data["job_id"]
        assert output.content_type == "movie_list"
        assert output.items is not None
        assert len(output.items) == 3
        assert output.confidence == data["confidence"]
        assert output.recipe is None
        assert output.script is None

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            FinalOutput.model_validate(
                {
                    "job_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                    "content_type": "invalid_type",
                    "video_metadata": {},
                    "confidence": -0.5,
                    "provenance": [],
                    "processed_at": "2026-04-20T06:45:00Z",
                    "processing_duration_seconds": 100.0,
                }
            )


# ── AuthToken ─────────────────────────────────────────


class TestAuthToken:
    """Tests for AuthToken schema validation."""

    def test_valid_fixture(self) -> None:
        data = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example.signature",
            "token_type": "bearer",
            "expires_in": 3600,
        }
        token = AuthToken.model_validate(data)
        assert token.access_token == data["access_token"]
        assert token.token_type == "bearer"
        assert token.expires_in == 3600

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            AuthToken.model_validate(
                {
                    "access_token": "some_token",
                    "token_type": "not_bearer",
                    "expires_in": "not_an_int",
                }
            )


# ── JWTPayload ────────────────────────────────────────


class TestJWTPayload:
    """Tests for JWTPayload schema validation."""

    def test_valid_fixture(self) -> None:
        data = {
            "sub": "user_abc123",
            "exp": 1745136000,
            "iat": 1745132400,
            "jti": "tok_7f3a9b2c4d5e6f00",
        }
        payload = JWTPayload.model_validate(data)
        assert payload.sub == "user_abc123"
        assert payload.exp == 1745136000
        assert payload.iat == 1745132400
        assert payload.jti == "tok_7f3a9b2c4d5e6f00"

    def test_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            JWTPayload.model_validate(
                {
                    "sub": 12345,
                    "exp": "not_a_timestamp",
                    "iat": None,
                }
            )
