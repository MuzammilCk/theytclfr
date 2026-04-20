import uuid
from datetime import datetime, timezone
import typing
from sqlalchemy import String, Text, Float, JSON, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from ytclfr.db.base import Base

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    youtube_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    local_media_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Using typing.Any for JSON to be flexible, but dictionary typically. 
    # Mapped[dict | list | None] sometimes causes issues with mypy if not defined well.
    metadata_raw: Mapped[dict[str, typing.Any] | list[typing.Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )
