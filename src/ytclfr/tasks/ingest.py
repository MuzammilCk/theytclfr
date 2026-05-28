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
def download_video(self: Any, job_id: str, pipeline_version: str = "v2") -> dict[str, Any]:
    settings_local = get_settings()
    parsed_job_id = uuid.UUID(job_id)
    temp_manager = TempStorageManager(settings_local)
    job_dir_created = False

    with db_session() as session:
        try:
            job = session.query(Job).filter(Job.id == parsed_job_id).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.s3_video_uri is not None and job.status not in ["pending", "downloading"]:
                logger.info("Idempotency hit: video already in S3")
                if pipeline_version == "v3":
                    from ytclfr.tasks.v3.stage_a_census import v3_run_signal_census
                    v3_run_signal_census.delay(job_id)
                else:
                    from ytclfr.tasks.stage_a import run_signal_census
                    run_signal_census.delay(job_id)
                return {"job_id": job_id, "status": "downloaded"}

            job.status = "downloading"
            session.commit()

            temp_manager.get_job_dir(parsed_job_id)
            job_dir_created = True

            downloader = VideoDownloader(settings_local)
            result = downloader.download(
                job.youtube_url, parsed_job_id, temp_manager.base_path
            )

            extract_metadata_safe(result.video_path)

            job.status = "upload_pending"
            job.video_title = result.title
            job.channel_name = result.channel
            job.duration_seconds = result.duration_seconds
            job.thumbnail_url = result.thumbnail_url
            job.local_media_path = str(result.video_path)  # Temporarily store local path for upload task
            job.metadata_raw = result.metadata_raw

            session.commit()

            upload_video_to_s3.delay(job_id, str(result.video_path), pipeline_version=pipeline_version)
            
            return {"job_id": job_id, "status": "upload_pending"}

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

@celery_app.task(  # type: ignore
    bind=True,
    name="ytclfr.ingest.upload_video",
    queue="io",
    max_retries=5,
    default_retry_delay=60,
)
def upload_video_to_s3(self: Any, job_id: str, local_video_path: str, pipeline_version: str = "v2") -> dict[str, Any]:
    settings_local = get_settings()
    parsed_job_id = uuid.UUID(job_id)
    temp_manager = TempStorageManager(settings_local)

    with db_session() as session:
        try:
            job = session.query(Job).filter(Job.id == parsed_job_id).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.s3_video_uri is not None:
                logger.info("Idempotency hit: video already in S3")
                temp_manager.cleanup_job(parsed_job_id)
                if pipeline_version == "v3":
                    from ytclfr.tasks.v3.stage_a_census import v3_run_signal_census
                    v3_run_signal_census.delay(job_id)
                else:
                    from ytclfr.tasks.stage_a import run_signal_census
                    run_signal_census.delay(job_id)
                return {"job_id": job_id, "status": "downloaded"}

            # Phase 10: Upload video to S3 and clear local path
            from ytclfr.ingestion.s3_storage import S3StorageManager

            s3_manager = S3StorageManager(settings_local)
            s3_object_key = f"{job_id}/video.mp4"
            from pathlib import Path
            s3_uri = s3_manager.upload_file(Path(local_video_path), s3_object_key)

            job.status = "downloaded"
            job.s3_video_uri = s3_uri
            job.local_media_path = None  # Clear local path, it's in S3 now

            session.commit()

            # Immediately delete local video file — the ingestion node
            # must not retain the video after S3 upload (DR-18).
            temp_manager.cleanup_job(parsed_job_id)

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

            if pipeline_version == "v3":
                from ytclfr.tasks.v3.stage_a_census import v3_run_signal_census
                v3_run_signal_census.delay(job_id)
            else:
                from ytclfr.tasks.stage_a import run_signal_census
                run_signal_census.delay(job_id)

            return {"job_id": job_id, "status": "downloaded"}

        except Exception as exc:
            session.rollback()
            if self.request.retries >= self.max_retries:
                job = session.query(Job).filter(Job.id == parsed_job_id).first()
                if job:
                    job.status = "dead_letter"
                    job.error_message = str(exc)
                    session.commit()
                temp_manager.cleanup_job(parsed_job_id)

            raise self.retry(exc=exc)


def extract_metadata_safe(video_path: Any) -> None:
    """Wrapper to call metadata extraction without failing ingestion."""
    try:
        from ytclfr.ingestion.metadata import extract_metadata

        extract_metadata(video_path)
    except Exception as exc:
        logger.warning("Metadata extraction failed (non-fatal): %s", exc)
