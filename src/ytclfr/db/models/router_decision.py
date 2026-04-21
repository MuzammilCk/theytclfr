"""SQLAlchemy ORM model for router_decisions table."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ytclfr.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class RouterDecisionModel(Base):
    """Stores the preflight router classification for each job."""

    __tablename__ = "router_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id"), nullable=False, unique=True
    )
    primary_route: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    speech_density: Mapped[float] = mapped_column(Float, nullable=False)
    ocr_density: Mapped[float] = mapped_column(Float, nullable=False)
    routing_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (Index("ix_router_decisions_job_id", "job_id"),)
