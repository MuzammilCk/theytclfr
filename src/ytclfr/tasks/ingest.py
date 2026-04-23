import uuid
from datetime import UTC, datetime
from typing import Any

from ytclfr.contracts.events import VideoIngestedEvent
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.ingestion.downloader import IngestionError, VideoDownloader
from ytclfr.ingestion.metadata import extract_metadata
from ytclfr.ingestion.temp_storage import TempStorageManager
from ytclfr.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(  # type: ignore
    bind=True,
    name="ytclfr.ingest.download_video",
    queue="heavy",
    max_retries=3,
    default_retry_delay=30,
)
def download_video(self: Any, job_id: str) -> dict[str, Any]:
    settings_local = get_settings()
    parsed_job_id = uuid.UUID(job_id)
    temp_manager = TempStorageManager(settings_local)
    job_dir_created = False

    with db_session() as session:
        try:
            job = session.query(Job).filter(Job.id == parsed_job_id).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            job.status = "downloading"
            session.commit()

            temp_manager.get_job_dir(parsed_job_id)
            job_dir_created = True

            downloader = VideoDownloader(settings_local)
            result = downloader.download(
                job.youtube_url, parsed_job_id, temp_manager.base_path
            )

            extract_metadata(result.video_path)

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
                ingested_at=datetime.now(UTC),
                metadata_raw=job.metadata_raw,
            )
            logger.info(f"VideoIngestedEvent: {event.model_dump_json()}")
            # PHASE-5-TODO: publish VideoIngestedEvent to Redis pub/sub

            from ytclfr.tasks.route import classify_video

            classify_video.apply_async(
                args=[job_id],
                countdown=2,
            )
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
