"""V2 output contracts for Stage D — Taxonomy + Intent Mapping.

V2FinalOutput is the terminal output of the V2 pipeline.
It is stored in the existing final_outputs table (output_json
column) with content_type = "v2_" + parent_category.

The V1 FinalOutput contract (contracts/output.py) is NOT modified.
V1 API endpoint updates are deferred to Pipeline Wiring (W-6).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaxonomyResult(BaseModel):
    """Taxonomy classification produced by Stage D."""

    model_config = ConfigDict(frozen=True)

    parent_category: str = Field(
        description=(
            "Top-level category: Education, Shopping, Sports, Music, "
            "Film, Technology, Food, Health, News, Other"
        )
    )
    child_category: str = Field(
        description="Specific subcategory within the parent"
    )
    intent: str = Field(
        description="What the creator intends the viewer to achieve"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Taxonomy confidence 0.0–1.0",
    )
    groq_taxonomy_used: bool = Field(
        default=False,
        description="True if Groq produced this taxonomy",
    )


class ExtractedItem(BaseModel):
    """A structured item extracted from the video content.

    Populated from EvidenceGraph entities with type refinement.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    item_type: Literal["product", "person", "place", "topic"]
    timestamp: float | None = Field(
        default=None,
        description="First mention timestamp in seconds",
    )
    confidence: float = Field(ge=0.0, le=1.0)


class V2FinalOutput(BaseModel):
    """Terminal output of the V2 evidence-based pipeline.

    Produced by Stage D and persisted to final_outputs.output_json.
    Contains the complete taxonomy, summary, structured items,
    evidence provenance, and field-level confidence scores.
    """

    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    taxonomy: TaxonomyResult
    summary: str = Field(
        description="2-3 sentence video summary from Stage C Groq"
    )
    items: list[ExtractedItem] = Field(
        default_factory=list,
        description="Structured items extracted from the video",
    )
    evidence_graph_summary: list[dict] = Field(
        default_factory=list,
        description="Sample of fused segments for provenance",
    )
    provenance: dict = Field(
        default_factory=dict,
        description="Links taxonomy claims to evidence timestamps",
    )
    confidence: dict = Field(
        default_factory=dict,
        description=(
            "Field-level confidence: taxonomy, summary, items, overall"
        ),
    )
    fallback_notes: list[str] = Field(
        default_factory=list,
        description="Notes when rule-based fallback was used",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence_fields(cls, v: dict) -> dict:
        """All confidence sub-values must be 0.0–1.0."""
        for key, val in v.items():
            if isinstance(val, float) and not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"confidence.{key} must be between 0.0 and 1.0"
                )
        return v
