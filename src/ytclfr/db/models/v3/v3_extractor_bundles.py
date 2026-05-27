import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from ytclfr.db.base import Base


class V3ExtractorBundleORM(Base):
    """SQLAlchemy ORM for v3_extractor_bundles table."""

    __tablename__ = "v3_extractor_bundles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    asr_segments_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="[]")
    ocr_segments_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="[]")
    audio_segments_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="[]")
    asr_metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index(
            "ix_v3_extractor_bundles_job_id",
            "job_id",
        ),
    )
