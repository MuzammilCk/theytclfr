"""SQLAlchemy ORM model for the signal_manifests table.

ytclfr V2 — Stage A: Signal Census.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ytclfr.db.base import Base


class SignalManifestORM(Base):
    """SQLAlchemy ORM for signal_manifests table."""

    __tablename__ = "signal_manifests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audio_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    language: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    has_speech: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    has_music: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    has_burned_in_text: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    has_subtitle_track: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    has_faces: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    motion_density: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    motion_score: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    aspect_ratio: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="unknown"
    )
    content_format: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="unknown"
    )
    scene_cut_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    duration_seconds: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    probing_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
