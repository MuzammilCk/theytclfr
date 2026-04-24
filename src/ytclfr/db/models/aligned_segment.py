import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from ytclfr.db.base import Base

DEFAULT_EMBEDDING_DIM: int = 768  # Must match EMBEDDING_DIM in .env


class AlignedSegmentModel(Base):
    __tablename__ = "aligned_segments"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False, index=True
    )
    start_seconds: Mapped[float] = mapped_column(sa.Float, nullable=False)
    end_seconds: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(DEFAULT_EMBEDDING_DIM), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=func.now(),
    )
