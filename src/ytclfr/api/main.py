from fastapi import FastAPI
from ytclfr.api.v1.router import v1_router
from ytclfr.core.config import get_settings
from ytclfr.core.logging import configure_logging
from pathlib import Path

def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    
    app = FastAPI(title="ytclfr API", version="0.1.0")
    app.include_router(v1_router, prefix="/api/v1")
    
    @app.on_event("startup")
    async def startup_event() -> None:
        Path(settings.temp_media_path).mkdir(parents=True, exist_ok=True)
        
    return app

app = create_app()
