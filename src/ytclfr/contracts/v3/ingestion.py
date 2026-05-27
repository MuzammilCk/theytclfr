"""V3 Ingestion Contract.

Defines the output of the ingestion phase, passing 
strict URIs and metadata to Stage A.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngestionResult(BaseModel):
    """Result of video ingestion and upload.
    
    Acts as the entry point contract for Stage A (Signal Census).
    """

    model_config = ConfigDict(frozen=True)

    job_id: UUID
    youtube_url: str = Field(description="Normalized YouTube URL")
    s3_video_uri: str = Field(description="S3 URI where the video is stored")
    video_title: str | None = None
    channel_name: str | None = None
    duration_seconds: float = Field(ge=0.0)
    thumbnail_url: str | None = None
    metadata_raw: dict | list | None = Field(
        default=None,
        description="Raw yt-dlp metadata payload",
    )
    ingested_at: datetime = Field(
        default_factory=datetime.utcnow
    )
