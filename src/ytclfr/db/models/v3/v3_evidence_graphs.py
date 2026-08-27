import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from ytclfr.db.base import Base


class V3EvidenceGraphORM(Base):
    """SQLAlchemy ORM for v3_evidence_graphs table."""

    __tablename__ = "v3_evidence_graphs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )
    segments_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    entities_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    dominant_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    groq_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_boundaries_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    groq_reasoning_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    modality_coverage_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    conflict_details_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="[]")
    structural_video_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="none")
    evidence_priority_notes_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="[]")
    primary_evidence_modality: Mapped[str] = mapped_column(Text, nullable=False, server_default="mixed")
    total_segments: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
