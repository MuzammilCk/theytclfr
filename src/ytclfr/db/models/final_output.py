import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ytclfr.db.base import Base


class FinalOutputModel(Base):
    __tablename__ = "final_outputs"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False, unique=True
    )
    content_type: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    overall_confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=func.now(),
        onupdate=func.now(),
    )
