"""Event schemas for the ytclfr pipeline."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
