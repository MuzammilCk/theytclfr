"""Extractor result schemas for the ytclfr pipeline."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ExtractorResultType = Literal["asr", "ocr", "audio"]


class ASRSegment(BaseModel):
    """A single ASR transcript segment with word-level timestamps."""

    segment_type: Literal["asr"] = "asr"
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

    segment_type: Literal["ocr"] = "ocr"
    frame_timestamp: float = Field(ge=0.0)
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_boxes: list[dict[str, object]] | None = None

    model_config = {
        "frozen": True,
    }


class AudioSegment(BaseModel):
    """Audio classification result from metadata or acoustic analysis."""

    segment_type: Literal["audio"] = "audio"
    label: str  # "speech", "music", "no_audio"
    confidence: float = Field(ge=0.0, le=1.0)
    codec: str | None = None
    bitrate_kbps: float | None = None

    model_config = {
        "frozen": True,
    }


class ExtractorResult(BaseModel):
    """Result container for an extractor run (ASR, OCR, or audio classification)."""

    job_id: UUID
    extractor_type: ExtractorResultType
    segments: list[
        Annotated[
            ASRSegment | OCRSegment | AudioSegment,
            Field(discriminator="segment_type"),
        ]
    ]
    total_duration_seconds: float = Field(ge=0.0)
    extracted_at: datetime
    error: str | None = None

    model_config = {
        "frozen": True,
    }
