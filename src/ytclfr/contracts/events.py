"""Event schemas for the ytclfr pipeline."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VideoIngestedEvent(BaseModel):
    """Event emitted when a YouTube video has been successfully ingested."""

    job_id: UUID
    youtube_url: str
    video_title: str
    channel_name: str
    duration_seconds: float
    thumbnail_url: str | None = None
    local_media_path: str | None = None
    ingested_at: datetime
    metadata_raw: dict[str, object]

    model_config = {
        "frozen": True,
    }


# ── Stage A — Signal Census events ────────────────────────────────

from enum import Enum

from pydantic import ConfigDict


class StageAStatus(str, Enum):
    """Status codes for Stage A signal census lifecycle."""

    STARTED = "stage_a_started"
    PROBE_AUDIO_COMPLETE = "stage_a_probe_audio_complete"
    PROBE_VISUAL_COMPLETE = "stage_a_probe_visual_complete"
    PROBE_METADATA_COMPLETE = "stage_a_probe_metadata_complete"
    COMPLETE = "stage_a_complete"
    FAILED = "stage_a_failed"


class StageAEvent(BaseModel):
    """SSE event emitted by tasks/stage_a.py."""

    model_config = ConfigDict(use_enum_values=True)

    event_type: StageAStatus
    job_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    manifest_id: str | None = None
    error: str | None = None
    details: dict = Field(default_factory=dict)
