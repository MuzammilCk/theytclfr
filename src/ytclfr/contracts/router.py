"""Router decision schema for the ytclfr pipeline."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RouterDecision(BaseModel):
    """Decision output from the preflight content router."""

    job_id: UUID
    primary_route: Literal[
        "speech-heavy",
        "music-heavy",
        "list-edit",
        "slide-presentation",
        "mixed",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    speech_density: float = Field(ge=0.0, le=1.0)
    ocr_density: float = Field(ge=0.0, le=1.0)
    decided_at: datetime
    routing_notes: str | None = None

    model_config = {
        "frozen": True,
    }
