from fastapi import APIRouter
from pydantic import BaseModel

from ytclfr.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", environment=settings.environment)
