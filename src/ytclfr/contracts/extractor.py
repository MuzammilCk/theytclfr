"""Extractor result schemas for the ytclfr pipeline."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ExtractorResultType = Literal["asr", "ocr"]


class ASRSegment(BaseModel):
    """A single ASR transcript segment with word-level timestamps."""

    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    words: list[dict[str, object]]

    model_config = {
        "frozen": True,
    }


class OCRSegment(BaseModel):
    """A single OCR extraction from a video frame."""

    frame_timestamp: float = Field(ge=0.0)
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_boxes: list[dict[str, object]] | None = None

    model_config = {
        "frozen": True,
    }


class ExtractorResult(BaseModel):
    """Result container for an extractor run (ASR or OCR)."""

    job_id: UUID
    extractor_type: ExtractorResultType
    segments: list[ASRSegment] | list[OCRSegment]
    total_duration_seconds: float = Field(ge=0.0)
    extracted_at: datetime
    error: str | None = None

    model_config = {
        "frozen": True,
    }
