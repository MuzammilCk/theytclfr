from ytclfr.queue.celery_app import celery_app
from ytclfr.core.config import get_settings
from ytclfr.db.session import get_db
from ytclfr.db.models.job import Job
from ytclfr.ingestion.temp_storage import TempStorageManager
from ytclfr.ingestion.downloader import VideoDownloader, IngestionError
from ytclfr.ingestion.metadata import extract_metadata
from ytclfr.contracts.events import VideoIngestedEvent
from ytclfr.core.logging import get_logger
import uuid
from typing import Any
from datetime import datetime, timezone

logger = get_logger(__name__)
settings = get_settings()

@celery_app.task(
    bind=True,
    name="ytclfr.ingest.download_video",
    queue="heavy",
    max_retries=3,
    default_retry_delay=30,
    time_limit=settings.celery_task_time_limit,
)
def download_video(self, job_id: str) -> dict[str, Any]:
    settings_local = get_settings()
    parsed_job_id = uuid.UUID(job_id)
    temp_manager = TempStorageManager(settings_local)
    job_dir_created = False
    
    db_gen = get_db()
    session = next(db_gen)

    try:
        job = session.query(Job).filter(Job.id == parsed_job_id).first()
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        job.status = "downloading"
        session.commit()

        job_dir = temp_manager.get_job_dir(parsed_job_id)
        job_dir_created = True

        downloader = VideoDownloader(settings_local)
        result = downloader.download(job.youtube_url, parsed_job_id, temp_manager.base_path)

        metadata = extract_metadata(result.video_path)

        job.status = "downloaded"
        job.video_title = result.title
        job.channel_name = result.channel
        job.duration_seconds = result.duration_seconds
        job.thumbnail_url = result.thumbnail_url
        job.local_media_path = str(result.video_path)
        job.metadata_raw = result.metadata_raw
        
        session.commit()

        event = VideoIngestedEvent(
            job_id=parsed_job_id,
            youtube_url=job.youtube_url,
            video_title=job.video_title,
            channel_name=job.channel_name,
            duration_seconds=job.duration_seconds,
            local_media_path=job.local_media_path,
            ingested_at=datetime.now(timezone.utc),
            metadata_raw=job.metadata_raw,
        )
        logger.info(f"VideoIngestedEvent: {event.model_dump_json()}")
        # PHASE-5-TODO: publish VideoIngestedEvent to Redis pub/sub channel when worker infrastructure is built

        return {"job_id": job_id, "status": "downloaded"}

    except IngestionError as e:
        session.rollback()
        job = session.query(Job).filter(Job.id == parsed_job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            session.commit()
        if job_dir_created:
            temp_manager.cleanup_job(parsed_job_id)
        return {"job_id": job_id, "status": "failed", "error": str(e)}

    except Exception as exc:
        session.rollback()
        job = session.query(Job).filter(Job.id == parsed_job_id).first()
        if job:
            job.status = "failed"
            if self.request.retries >= self.max_retries:
                job.error_message = str(exc)
            session.commit()
            
        if self.request.retries >= self.max_retries and job_dir_created:
             temp_manager.cleanup_job(parsed_job_id)
             
        raise self.retry(exc=exc)

    finally:
        session.close()
