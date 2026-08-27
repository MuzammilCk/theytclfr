from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.ingestion.temp_storage import TempStorageManager
from ytclfr.queue.celery_app import celery_app

logger = get_logger(__name__)

@celery_app.task(name="ytclfr.tasks.cleanup.cleanup_orphaned_s3", queue="fast")
def cleanup_orphaned_s3() -> dict[str, object]:
    """Clean up expired temporary job directories."""
    settings = get_settings()
    manager = TempStorageManager(settings)
    count = manager.cleanup_expired()
    logger.info("Cleaned up %d expired temporary job directories", count)
    return {"cleaned_count": count}
