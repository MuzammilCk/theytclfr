"""Output schemas for the ytclfr pipeline."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ContentType = Literal[
    "recipe",
    "movie_list",
    "book_list",
    "song_list",
    "product_list",
    "script",
    "summary",
    "mixed",
]


class RecipeItem(BaseModel):
    """A structured recipe extracted from video content."""

    name: str
    ingredients: list[str]
    steps: list[str]
    timestamp: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = {
        "frozen": True,
    }


class ListItem(BaseModel):
    """A single item from a structured list (movies, books, songs, products)."""

    title: str
    context: str | None = None
    timestamp: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, object] | None = None

    model_config = {
        "frozen": True,
    }


class ScriptSegment(BaseModel):
    """A segment of a script or spoken content with speaker attribution."""

    timestamp: float = Field(ge=0.0)
    end_timestamp: float | None = None
    text: str
    speaker: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = {
        "frozen": True,
    }


class FinalOutput(BaseModel):
    """Final structured output for a processed video job."""

    job_id: UUID
    content_type: ContentType
    video_metadata: dict[str, object]
    items: list[ListItem] | None = None
    recipe: RecipeItem | None = None
    script: list[ScriptSegment] | None = None
    summary: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: list[dict[str, object]]
    processed_at: datetime
    processing_duration_seconds: float = Field(ge=0.0)

    model_config = {
        "frozen": True,
    }
