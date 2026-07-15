"""V3 Data contracts for Stage C — Evidence Fusion.

EvidenceGraph is the single output of Stage C.
It holds the aligned timeline, extracted entities, and
Groq-derived semantic insights.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FusedSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: float = Field(ge=0.0)
    end_timestamp: float | None = None
    text: str
    source: Literal["asr", "ocr", "merged", "audio"]
    confidence: float = Field(ge=0.0, le=1.0)
    entity_refs: list[str] = Field(default_factory=list)


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Entity name as found in transcript")
    entity_type: Literal[
        "product", "person", "place", "topic", "unknown"
    ] = Field(description="Entity classification")
    mentioned_at: list[float]
    confidence: float = Field(ge=0.0, le=1.0)


class EvidenceGraph(BaseModel):
    """Fused evidence produced by Stage C (V3)."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    job_id: UUID
    segments: list[FusedSegment]
    entities: list[ExtractedEntity]
    dominant_subject: str | None = None
    groq_summary: str | None = None
    scene_boundaries: list[float] = Field(default_factory=list)
    groq_reasoning_used: bool = False
    
    modality_coverage: dict[str, float] = Field(default_factory=dict)
    conflict_count: int = Field(default=0, ge=0)
    conflict_details: list[dict[str, Any]] = Field(default_factory=list)
    
    structural_video_type: str = "none"
    evidence_priority_notes: list[str] = Field(default_factory=list)
    primary_evidence_modality: str = "mixed"
    
    total_segments: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v
