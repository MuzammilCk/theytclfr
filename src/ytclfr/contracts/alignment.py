"""Alignment schemas for the ytclfr pipeline."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SegmentSource = Literal["asr", "ocr", "merged"]


class AlignedSegment(BaseModel):
    """A single segment in the unified aligned timeline."""

    timestamp: float = Field(ge=0.0)
    end_timestamp: float | None = None
    source: SegmentSource
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    original_segment_ids: list[str]

    model_config = {
        "frozen": True,
    }


class AlignedTimeline(BaseModel):
    """Complete aligned timeline combining ASR, OCR, and merged evidence."""

    job_id: UUID
    segments: list[AlignedSegment]
    total_segments: int = Field(ge=0)
    has_gaps: bool
    aligned_at: datetime

    model_config = {
        "frozen": True,
    }
