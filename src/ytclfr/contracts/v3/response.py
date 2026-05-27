"""V3 Final Response Contract.

The pristine, client-facing JSON object returned by the V3 API.
Does not include internal state unless requested via Resource Views.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaxonomyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_category: str
    child_category: str
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    groq_taxonomy_used: bool = False


class ExtractedItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    item_type: Literal["product", "person", "place", "topic"]
    timestamp: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class FinalResponse(BaseModel):
    """Terminal client-facing output for V3."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    job_id: UUID
    taxonomy: TaxonomyResult
    summary: str
    items: list[ExtractedItem] = Field(default_factory=list)
    confidence: dict = Field(default_factory=dict)
    fallback_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("confidence")
    @classmethod
    def validate_confidence_fields(cls, v: dict) -> dict:
        for key, val in v.items():
            if isinstance(val, float) and not (0.0 <= val <= 1.0):
                raise ValueError(f"confidence.{key} must be between 0.0 and 1.0")
        return v
