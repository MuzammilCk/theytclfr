"""Data contract for Stage A — Signal Census.

SignalManifest is the single output of Stage A. Every field represents
a detected physical signal — not a classification guess.  Stage B reads
this manifest to decide which extractors to run.

Pure Pydantic v2 only.  No Celery, SQLAlchemy, or task imports.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignalManifest(BaseModel):
    """Evidence manifest produced by Stage A signal probing.

    This is the single output of Stage A. Every field is a
    detected physical signal — not a classification guess.
    Stage B reads this manifest to decide which extractors to run.
    """

    model_config = ConfigDict(from_attributes=True)

    job_id: UUID = Field(description="Job this manifest belongs to")
    audio_type: Literal[
        "speech_only",
        "music_only",
        "speech_music",
        "sfx",
        "ambient",
        "silent",
    ] = Field(description="Dominant audio character detected")
    language: str | None = Field(
        default=None,
        description="ISO 639-1 code if detected, else None",
    )
    has_speech: bool = Field(description="VAD detected voiced frames")
    has_music: bool = Field(
        description="Beat/spectral music signal present"
    )
    has_burned_in_text: bool = Field(
        description="Structural subtitle-bar pattern in frames"
    )
    has_subtitle_track: bool = Field(
        description="yt-dlp reported a subtitle track in metadata"
    )
    has_faces: bool = Field(
        description="Haar cascade found faces in >= 3 sampled frames"
    )
    motion_density: float = Field(
        description="Scene cuts per minute (0.0 if no cuts)"
    )
    motion_score: float = Field(
        description="Normalised frame-diff intensity, 0.0–1.0"
    )
    aspect_ratio: str = Field(
        description="e.g. 16:9, 9:16, 1:1, unknown"
    )
    content_format: Literal[
        "live_action",
        "animation",
        "screen_recording",
        "mixed",
        "unknown",
    ] = Field(
        description="Inferred content format from visual heuristics"
    )
    scene_cut_count: int = Field(
        description="Raw count of detected scene cuts"
    )
    duration_seconds: float = Field(
        description="Video duration from metadata or audio probe"
    )
    probing_confidence: float = Field(
        description=(
            "Average of audio/visual/metadata probe confidence scores"
        )
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when manifest was created",
    )

    @field_validator("probing_confidence")
    @classmethod
    def validate_probing_confidence(cls, v: float) -> float:
        """Probing confidence must be between 0.0 and 1.0 inclusive."""
        if v < 0.0 or v > 1.0:
            raise ValueError(
                f"probing_confidence must be between 0.0 and 1.0, "
                f"got {v}"
            )
        return v

    @field_validator("motion_score")
    @classmethod
    def validate_motion_score(cls, v: float) -> float:
        """Motion score must be between 0.0 and 1.0 inclusive."""
        if v < 0.0 or v > 1.0:
            raise ValueError(
                f"motion_score must be between 0.0 and 1.0, got {v}"
            )
        return v

    @field_validator("duration_seconds")
    @classmethod
    def validate_duration_seconds(cls, v: float) -> float:
        """Duration must be non-negative."""
        if v < 0.0:
            raise ValueError(
                f"duration_seconds must be >= 0.0, got {v}"
            )
        return v
