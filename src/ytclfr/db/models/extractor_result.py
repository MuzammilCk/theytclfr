import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ytclfr.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ExtractorResultModel(Base):
    __tablename__ = "extractor_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    extractor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # One job can have multiple results per type
    # (e.g., retry produces a new result).
    # The temporal alignment layer reads the latest
    # by created_at per (job_id, extractor_type).
    segments_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    total_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_extractor_results_job_extractor",
            "job_id",
            "extractor_type",
        ),
    )
