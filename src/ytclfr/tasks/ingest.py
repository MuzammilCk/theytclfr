import uuid
from datetime import UTC, datetime
from typing import Any

from ytclfr.contracts.events import VideoIngestedEvent
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.ingestion.downloader import IngestionError, VideoDownloader
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

            if job.s3_video_uri is not None and job.status not in ["pending", "downloading"]:
                logger.info("Idempotency hit: video already in S3")
                from ytclfr.tasks.route import classify_video
                classify_video.apply_async(args=[job_id], countdown=2)
                return {"job_id": job_id, "status": "downloaded"}

            temp_manager.get_job_dir(parsed_job_id)
            job_dir_created = True

            downloader = VideoDownloader(settings_local)
            result = downloader.download(
                job.youtube_url, parsed_job_id, temp_manager.base_path
            )

            extract_metadata_safe(result.video_path)

            # Phase 10: Upload video to S3 and clear local path
            from ytclfr.ingestion.s3_storage import S3StorageManager

            s3_manager = S3StorageManager(settings_local)
            s3_object_key = f"{job_id}/video.mp4"
            s3_uri = s3_manager.upload_file(result.video_path, s3_object_key)

            job.status = "downloaded"
            job.video_title = result.title
            job.channel_name = result.channel
            job.duration_seconds = result.duration_seconds
            job.thumbnail_url = result.thumbnail_url
            job.s3_video_uri = s3_uri
            job.local_media_path = None  # Not reliable across nodes
            job.metadata_raw = result.metadata_raw

            session.commit()

            # Immediately delete local video file — the ingestion node
            # must not retain the video after S3 upload (DR-18).
            if job_dir_created:
                temp_manager.cleanup_job(parsed_job_id)
                job_dir_created = False

            event = VideoIngestedEvent(
                job_id=parsed_job_id,
                youtube_url=job.youtube_url,
                video_title=job.video_title,
                channel_name=job.channel_name,
                duration_seconds=job.duration_seconds,
                local_media_path=None,
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
                if self.request.retries >= self.max_retries:
                    job.status = "dead_letter"
                    job.error_message = str(exc)
                else:
                    job.status = "failed"
                session.commit()

            if self.request.retries >= self.max_retries and job_dir_created:
                temp_manager.cleanup_job(parsed_job_id)

            raise self.retry(exc=exc)


def extract_metadata_safe(video_path: Any) -> None:
    """Wrapper to call metadata extraction without failing ingestion."""
    try:
        from ytclfr.ingestion.metadata import extract_metadata

        extract_metadata(video_path)
    except Exception as exc:
        logger.warning("Metadata extraction failed (non-fatal): %s", exc)
