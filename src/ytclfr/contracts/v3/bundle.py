"""V3 Extractor Bundle Contract.

Defines the output of Stage B targeted extraction.
Includes the raw segments and completeness metrics like
untranscribed_speech_ratio for the VAD-to-Transcription Yield heuristic.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ASRSegment(BaseModel):
    segment_type: Literal["asr"] = "asr"
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    words: list[dict[str, object]]

    model_config = ConfigDict(frozen=True)


class OCRSegment(BaseModel):
    segment_type: Literal["ocr"] = "ocr"
    frame_timestamp: float = Field(ge=0.0)
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_boxes: list[dict[str, object]] | None = None

    model_config = ConfigDict(frozen=True)


class AudioSegment(BaseModel):
    segment_type: Literal["audio"] = "audio"
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    codec: str | None = None
    bitrate_kbps: float | None = None

    model_config = ConfigDict(frozen=True)


class ASRCompletenessMetrics(BaseModel):
    """Metrics to determine if ASR is heavily degraded."""
    total_vad_speech_ms: float = Field(ge=0.0)
    total_transcribed_ms: float = Field(ge=0.0)
    untranscribed_speech_ratio: float = Field(ge=0.0, le=1.0)
    max_untranscribed_segment_ms: float = Field(
        default=0.0, ge=0.0,
        description="Longest VAD segment that resulted in zero transcribed words",
    )
    is_degraded: bool = Field(
        default=False,
        description="True if ratio > 0.3 or max_untranscribed > 2500ms",
    )

    model_config = ConfigDict(frozen=True)


class ExtractorBundle(BaseModel):
    """Complete set of extractions from Stage B."""

    model_config = ConfigDict(frozen=True)

    job_id: UUID
    asr_segments: list[ASRSegment] = Field(default_factory=list)
    ocr_segments: list[OCRSegment] = Field(default_factory=list)
    audio_segments: list[AudioSegment] = Field(default_factory=list)
    
    asr_metrics: ASRCompletenessMetrics | None = Field(
        default=None,
        description="Completeness metrics, populated if ASR ran",
    )
    
    total_duration_seconds: float = Field(ge=0.0)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
