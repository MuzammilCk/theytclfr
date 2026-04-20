from pathlib import Path

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from ytclfr.api.rate_limit import limiter
from ytclfr.api.v1.router import v1_router
from ytclfr.core.config import get_settings
from ytclfr.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title="ytclfr API", version="0.1.0")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
    app.include_router(v1_router, prefix="/api/v1")

    @app.on_event("startup")
    async def startup_event() -> None:
        Path(settings.temp_media_path).mkdir(parents=True, exist_ok=True)

    return app


app = create_app()
