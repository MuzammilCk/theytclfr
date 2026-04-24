from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
import uuid

from fastapi import FastAPI, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from ytclfr.api.rate_limit import limiter
from ytclfr.api.v1.router import v1_router
from ytclfr.core.config import get_settings
from ytclfr.core.logging import configure_logging, trace_id_var


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = uuid.uuid4()
        trace_id_var.set(str(req_id))
        response = await call_next(request)
        response.headers["X-Trace-ID"] = str(req_id)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager.

    Handles application startup and shutdown logic.
    Replaces the deprecated @app.on_event("startup") pattern.

    Startup: ensures the temporary media directory exists.
    Shutdown: no cleanup needed in V1 (connections are managed
    per-request by the session context manager).
    """
    settings = get_settings()
    Path(settings.temp_media_path).mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown logic goes here if needed in future phases.


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="ytclfr API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore
    )
    app.add_middleware(TraceIdMiddleware)
    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()
