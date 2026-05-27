"""Data contracts for Stage C — Evidence Fusion.

EvidenceGraph is the single output of Stage C.
It holds the aligned timeline, extracted entities, and
Groq-derived semantic insights. Stage D reads this to
produce the final taxonomy and FinalOutput.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from typing_extensions import deprecated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FusedSegment(BaseModel):
    """One segment in the fused evidence timeline.

    Built from the V1 AlignedTimeline. Carries entity
    references added by Stage C's entity extractor.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: float = Field(ge=0.0)
    end_timestamp: float | None = None
    text: str
    source: Literal["asr", "ocr", "merged", "audio"]
    confidence: float = Field(ge=0.0, le=1.0)
    entity_refs: list[str] = Field(
        default_factory=list,
        description="Names of entities mentioned in this segment",
    )


class ExtractedEntity(BaseModel):
    """An entity extracted from the evidence timeline.

    Populated first by heuristic extraction, then refined
    by Groq if reasoning is available.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Entity name as found in transcript")
    entity_type: Literal[
        "product", "person", "place", "topic", "unknown"
    ] = Field(description="Entity classification")
    mentioned_at: list[float] = Field(
        description="Timestamps (seconds) where entity is mentioned"
    )
    confidence: float = Field(ge=0.0, le=1.0)


@deprecated("V2 legacy evidence contracts are deprecated and will be removed in 120 days.")
class EvidenceGraph(BaseModel):
    """Fused evidence produced by Stage C.

    The single output of Stage C, persisted to the
    evidence_graphs table. Stage D reads this to produce
    the final V2 taxonomy and FinalOutput.
    """

    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    segments: list[FusedSegment] = Field(
        description="Aligned timeline from V1 alignment engine"
    )
    entities: list[ExtractedEntity] = Field(
        description="Entities extracted and optionally refined by Groq"
    )
    dominant_subject: str | None = Field(
        default=None,
        description="What this video is primarily about (from Groq)",
    )
    groq_summary: str | None = Field(
        default=None,
        description="2-3 sentence summary produced by Groq",
    )
    scene_boundaries: list[float] = Field(
        default_factory=list,
        description="Timestamps of major topic shifts (from Groq)",
    )
    groq_reasoning_used: bool = Field(
        default=False,
        description="True if Groq was called and succeeded",
    )
    modality_coverage: dict[str, float] = Field(
        default_factory=dict,
        description="Coverage fraction per modality: {asr: 0.8, ocr: 0.3, visual: 1.0}",
    )
    conflict_count: int = Field(
        default=0, ge=0,
        description="Number of detected conflicts between modalities",
    )
    conflict_details: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Details of each modality conflict (timestamp, modalities, resolution)",
    )
    structural_video_type: str = Field(
        default="none",
        description="Propagated from SignalManifest for fusion context",
    )
    evidence_priority_notes: list[str] = Field(
        default_factory=list,
        description="Notes on which modality was prioritized and why",
    )
    primary_evidence_modality: str = Field(
        default="mixed",
        description="Dominant evidence source for this video: asr, ocr, visual, mixed",
    )
    total_segments: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Confidence must be 0.0–1.0."""
        if v < 0.0 or v > 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {v}"
            )
        return v
