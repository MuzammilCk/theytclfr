import uuid
from pathlib import Path
from typing import Any

from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.models.v3.v3_extractor_bundles import V3ExtractorBundle
from ytclfr.db.session import db_session
from ytclfr.extractors.base import BaseExtractorTask
from ytclfr.ingestion.temp_storage import TempStorageManager
from ytclfr.queue.celery_app import celery_app

logger = get_logger(__name__)

@celery_app.task(  # type: ignore
    bind=True,
    base=BaseExtractorTask,
    name="ytclfr.tasks.v3.v3_run_asr",
    queue="heavy",
)
def v3_run_asr(self: Any, job_id: str) -> dict[str, object]:
    """Run V3 ASR transcription on the downloaded video."""
    settings = get_settings()
    job_uuid = uuid.UUID(job_id)
    local_video_path: Path | None = None

    with db_session() as session:
        try:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")

            if not job.s3_video_uri:
                raise ValueError(
                    f"Job {job_id} has no S3 video URI — upload may have failed"
                )

            bundle = session.query(V3ExtractorBundle).filter_by(job_id=job_uuid).first()
            if bundle and bundle.asr_segments_json:
                logger.info("Idempotency hit: V3ExtractorBundle for ASR already exists")
                return {
                    "job_id": str(job_id),
                    "extractor_type": "asr",
                    "status": "success",
                }

            from ytclfr.ingestion.s3_storage import S3StorageManager

            s3_manager = S3StorageManager(settings)
            temp_manager = TempStorageManager(settings)
            local_dir = temp_manager.get_job_dir(job_uuid)
            local_video_path = local_dir / f"video_asr_{uuid.uuid4().hex}.mp4"

            s3_object_key = f"{job_id}/video.mp4"
            s3_manager.download_file(s3_object_key, local_video_path)

            from ytclfr.extractors.v3_asr import get_v3_asr_extractor

            extractor = get_v3_asr_extractor()
            segments, metrics, duration = extractor.extract(
                job_id=job_uuid,
                video_path=local_video_path,
            )
            
            # Find or create bundle
            if not bundle:
                bundle = V3ExtractorBundle(job_id=job_uuid)
                session.add(bundle)

            bundle.asr_segments_json = [s.model_dump() for s in segments]
            bundle.asr_metrics_json = metrics.model_dump()
            session.commit()

            logger.info(
                "V3 ASR extraction complete for job %s: %d segments",
                job_id,
                len(segments),
            )
            return {
                "job_id": str(job_id),
                "extractor_type": "asr",
                "status": "success",
            }

        except Exception as exc:
            session.rollback()
            if self.request.retries >= self.max_retries:
                try:
                    job_obj = session.query(Job).filter(Job.id == job_uuid).first()
                    if job_obj:
                        job_obj.status = "dead_letter"
                        session.commit()
                except Exception:
                    pass
                logger.error(
                    "Extractor asr exhausted all retries for job %s: %s",
                    job_id,
                    str(exc),
                )
                return {
                    "job_id": str(job_id),
                    "extractor_type": "asr",
                    "status": "failed",
                }
            raise self.retry(exc=exc)

        finally:
            if local_video_path and local_video_path.exists():
                try:
                    local_video_path.unlink(missing_ok=True)
                except Exception as cleanup_exc:
                    logger.warning("Failed to clean up local file %s: %s", local_video_path, cleanup_exc)
