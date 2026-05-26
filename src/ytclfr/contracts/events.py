"""Event schemas for the ytclfr pipeline."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class StageAStatus(StrEnum):
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


# ── Stage B — Targeted Extraction events ──────────────────────


class StageBStatus(StrEnum):
    """Status codes for Stage B targeted extraction lifecycle."""

    STARTED = "stage_b_started"
    MANIFEST_LOADED = "stage_b_manifest_loaded"
    GROUP_BUILT = "stage_b_group_built"
    DISPATCHED = "stage_b_dispatched"
    FAILED = "stage_b_failed"


class StageBEvent(BaseModel):
    """SSE event emitted by tasks/stage_b.py."""

    model_config = ConfigDict(use_enum_values=True)

    event_type: StageBStatus
    job_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    extractors_dispatched: list[str] = Field(default_factory=list)
    error: str | None = None
    details: dict = Field(default_factory=dict)


# ── Stage C — Evidence Fusion events ──────────────────────────


class StageCStatus(StrEnum):
    """Status codes for Stage C evidence fusion lifecycle."""

    STARTED                 = "stage_c_started"
    ALIGNMENT_COMPLETE      = "stage_c_alignment_complete"
    ENTITIES_EXTRACTED      = "stage_c_entities_extracted"
    GROQ_COMPLETE           = "stage_c_groq_complete"
    GROQ_SKIPPED            = "stage_c_groq_skipped"
    COMPLETE                = "stage_c_complete"
    FAILED                  = "stage_c_failed"


class StageCEvent(BaseModel):
    """SSE event emitted by tasks/stage_c.py."""
"""Event schemas for the ytclfr pipeline."""

from datetime import datetime
from enum import Enum, StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VideoIngestedEvent(BaseModel):
    """Event emitted when a YouTube video has been successfully ingested."""

    job_id: UUID
    youtube_url: str
    video_title: str | None = None
    channel_name: str | None = None
    duration_seconds: float | None = None
    thumbnail_url: str | None = None
    local_media_path: str | None = None
    ingested_at: datetime
    metadata_raw: dict | list | None = None

    model_config = {
        "frozen": True,
    }


# ── Stage A — Signal Census events ────────────────────────────────


class StageAStatus(StrEnum):
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


# ── Stage B — Targeted Extraction events ──────────────────────


class StageBStatus(StrEnum):
    """Status codes for Stage B targeted extraction lifecycle."""

    STARTED = "stage_b_started"
    MANIFEST_LOADED = "stage_b_manifest_loaded"
    GROUP_BUILT = "stage_b_group_built"
    DISPATCHED = "stage_b_dispatched"
    FAILED = "stage_b_failed"


class StageBEvent(BaseModel):
    """SSE event emitted by tasks/stage_b.py."""

    model_config = ConfigDict(use_enum_values=True)

    event_type: StageBStatus
    job_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    extractors_dispatched: list[str] = Field(default_factory=list)
    error: str | None = None
    details: dict = Field(default_factory=dict)


# ── Stage C — Evidence Fusion events ──────────────────────────


class StageCStatus(StrEnum):
    """Status codes for Stage C evidence fusion lifecycle."""

    STARTED                 = "stage_c_started"
    ALIGNMENT_COMPLETE      = "stage_c_alignment_complete"
    ENTITIES_EXTRACTED      = "stage_c_entities_extracted"
    GROQ_COMPLETE           = "stage_c_groq_complete"
    GROQ_SKIPPED            = "stage_c_groq_skipped"
    COMPLETE                = "stage_c_complete"
    FAILED                  = "stage_c_failed"


class StageCEvent(BaseModel):
    """SSE event emitted by tasks/stage_c.py."""

    model_config = ConfigDict(use_enum_values=True)

    event_type: StageCStatus
    job_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    evidence_graph_id: str | None = None
    error: str | None = None
    details: dict = Field(default_factory=dict)


# ── Stage D — Taxonomy + Intent Mapping events ─────────────────

class StageDStatus(str, Enum):
    """Status codes for Stage D taxonomy mapping lifecycle."""

    STARTED                = "stage_d_started"
    EVIDENCE_LOADED        = "stage_d_evidence_loaded"
    GROQ_TAXONOMY_COMPLETE = "stage_d_groq_taxonomy_complete"
    GROQ_TAXONOMY_SKIPPED  = "stage_d_groq_taxonomy_skipped"
    COMPLETE               = "stage_d_complete"
    FAILED                 = "stage_d_failed"

class StageDEvent(BaseModel):
    """SSE event emitted by tasks/stage_d.py."""

    model_config = ConfigDict(use_enum_values=True)

    event_type: StageDStatus
    job_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    taxonomy: dict = Field(default_factory=dict)
    error: str | None = None
    details: dict = Field(default_factory=dict)
