import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ytclfr.contracts.extractor import ExtractorResult
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.extractor_result import (
    ExtractorResultModel,
)
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.extractors.base import BaseExtractorTask
from ytclfr.ingestion.temp_storage import TempStorageManager
from ytclfr.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(  # type: ignore
    bind=True,
    base=BaseExtractorTask,
    name="ytclfr.extract.run_asr",
    queue="heavy",
)
def run_asr(self: Any, job_id: str) -> dict[str, object]:
    """Run ASR transcription on the downloaded video.

    Phase 10: Downloads video from S3 to a transient local path,
    runs ASR, persists result to DB, then deletes local file.
    Returns only a lightweight status dict (DR-20).
    """

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

            existing = session.query(ExtractorResultModel).filter_by(job_id=job_uuid, extractor_type="asr").first()
            if existing and not existing.error_message:
                logger.info("Idempotency hit: ExtractorResultModel for ASR already exists")
                return {
                    "job_id": str(job_id),
                    "extractor_type": "asr",
                    "status": "success",
                }

            # Download video from S3 to transient local path
            from ytclfr.ingestion.s3_storage import S3StorageManager

            s3_manager = S3StorageManager(settings)
            temp_manager = TempStorageManager(settings)
            local_dir = temp_manager.get_job_dir(job_uuid)
            local_video_path = local_dir / "video.mp4"

            s3_object_key = f"{job_id}/video.mp4"
            s3_manager.download_file(s3_object_key, local_video_path)

            from ytclfr.extractors.asr import (
                get_asr_extractor,
            )

            extractor = get_asr_extractor()
            result = extractor.extract(
                job_id=job_uuid,
                video_path=local_video_path,
            )

            _persist_extractor_result(session, result)
            session.commit()

            logger.info(
                "ASR extraction complete for job %s: %d segments",
                job_id,
                len(result.segments),
            )
            # Phase 10 (DR-20): Return lightweight dict only.
            # Full results are already persisted to extractor_results table.
            return {
                "job_id": str(job_id),
                "extractor_type": "asr",
                "status": "success",
            }

        except Exception as exc:
            session.rollback()
            if self.request.retries >= self.max_retries:
                _persist_extractor_error(session, job_uuid, "asr", str(exc))
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
            # Phase 10 Bugfix: Only unlink the specific file this task downloaded
            # to avoid race conditions with parallel tasks sharing the job dir.
            if local_video_path and local_video_path.exists():
                try:
                    local_video_path.unlink(missing_ok=True)
                except Exception as cleanup_exc:
                    logger.warning("Failed to clean up local file %s: %s", local_video_path, cleanup_exc)


@celery_app.task(  # type: ignore
    bind=True,
    base=BaseExtractorTask,
    name="ytclfr.extract.run_ocr",
    queue="heavy",
)
def run_ocr(self: Any, job_id: str) -> dict[str, object]:
    """Run OCR frame extraction on the downloaded video.

    Phase 10: Downloads video from S3, extracts frames,
    runs OCR, persists to DB, deletes local files.
    Returns only a lightweight status dict (DR-20).
    """
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

            existing = session.query(ExtractorResultModel).filter_by(job_id=job_uuid, extractor_type="ocr").first()
            if existing and not existing.error_message:
                logger.info("Idempotency hit: ExtractorResultModel for OCR already exists")
                return {
                    "job_id": str(job_id),
                    "extractor_type": "ocr",
                    "status": "success",
                }

            # Download video from S3 to transient local path
            from ytclfr.ingestion.s3_storage import S3StorageManager

            s3_manager = S3StorageManager(settings)
            temp_manager = TempStorageManager(settings)
            local_dir = temp_manager.get_job_dir(job_uuid)
            local_video_path = local_dir / "video.mp4"
            ocr_frames_dir = local_dir / "ocr_frames"

            s3_object_key = f"{job_id}/video.mp4"
            s3_manager.download_file(s3_object_key, local_video_path)

            from ytclfr.extractors.ocr import (
                get_ocr_extractor,
            )

            extractor = get_ocr_extractor()
            result = extractor.extract(
                job_id=job_uuid,
                video_path=local_video_path,
                output_dir=ocr_frames_dir,
            )

            _persist_extractor_result(session, result)
            session.commit()

            logger.info(
                "OCR extraction complete for job %s: %d segments",
                job_id,
                len(result.segments),
            )
            # Phase 10 (DR-20): Return lightweight dict only.
            return {
                "job_id": str(job_id),
                "extractor_type": "ocr",
                "status": "success",
            }

        except Exception as exc:
            session.rollback()
            if self.request.retries >= self.max_retries:
                _persist_extractor_error(session, job_uuid, "ocr", str(exc))
                try:
                    job_obj = session.query(Job).filter(Job.id == job_uuid).first()
                    if job_obj:
                        job_obj.status = "dead_letter"
                        session.commit()
                except Exception:
                    pass
                logger.error(
                    "Extractor ocr exhausted all retries for job %s: %s",
                    job_id,
                    str(exc),
                )
                return {
                    "job_id": str(job_id),
                    "extractor_type": "ocr",
                    "status": "failed",
                }
            raise self.retry(exc=exc)

        finally:
            # Phase 10 Bugfix: Only unlink specific files.
            if local_video_path and local_video_path.exists():
                try:
                    local_video_path.unlink(missing_ok=True)
                except Exception as cleanup_exc:
                    logger.warning("Failed to clean up local file %s: %s", local_video_path, cleanup_exc)
            
            if 'ocr_frames_dir' in locals() and ocr_frames_dir.exists():
                import shutil
                shutil.rmtree(ocr_frames_dir, ignore_errors=True)


@celery_app.task(  # type: ignore
    bind=True,
    base=BaseExtractorTask,
    name="ytclfr.extract.run_audio_classifier",
    queue="fast",
)
def run_audio_classifier(self: Any, job_id: str) -> dict[str, object]:
    """Run audio type classification from metadata.

    Uses the yt-dlp metadata heuristic (V1).
    # PHASE-9-TODO: Replace with YAMNet.
    Runs on the fast queue — no heavy I/O.
    No S3 download needed — uses DB metadata only.
    """
    job_uuid = uuid.UUID(job_id)

    with db_session() as session:
        try:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")

            existing = session.query(ExtractorResultModel).filter_by(job_id=job_uuid, extractor_type="audio").first()
            if existing and not existing.error_message:
                logger.info("Idempotency hit: ExtractorResultModel for audio already exists")
                return {
                    "job_id": str(job_id),
                    "extractor_type": "audio",
                    "status": "success",
                }

            from ytclfr.extractors.audio_classifier import (
                classify_audio_from_metadata,
            )

            meta = job.metadata_raw if isinstance(job.metadata_raw, dict) else {}
            result = classify_audio_from_metadata(
                job_id=job_uuid,
                metadata_raw=meta,
            )

            _persist_extractor_result(session, result)
            session.commit()

            logger.info(
                "Audio classification complete for job %s: label=%s confidence=%.2f",
                job_id,
                result.segments[0].label if result.segments else "unknown",  # type: ignore[union-attr]
                result.segments[0].confidence if result.segments else 0.0,
            )
            # Phase 10 (DR-20): Return lightweight dict only.
            return {
                "job_id": str(job_id),
                "extractor_type": "audio",
                "status": "success",
            }

        except Exception as exc:
            session.rollback()
            if self.request.retries >= self.max_retries:
                _persist_extractor_error(session, job_uuid, "audio", str(exc))
                try:
                    job_obj = session.query(Job).filter(Job.id == job_uuid).first()
                    if job_obj:
                        job_obj.status = "dead_letter"
                        session.commit()
                except Exception:
                    pass
                logger.error(
                    "Extractor audio exhausted all retries for job %s: %s",
                    job_id,
                    str(exc),
                )
                return {
                    "job_id": str(job_id),
                    "extractor_type": "audio",
                    "status": "failed",
                }
            raise self.retry(exc=exc)


# ── Private helpers ────────────────────────────────


def _persist_extractor_result(
    session: Any,
    result: ExtractorResult,
) -> None:
    """Write ExtractorResultModel to DB session.
    Caller is responsible for commit.
    """
    db_result = ExtractorResultModel(
        job_id=result.job_id,
        extractor_type=result.extractor_type,
        segments_json={"segments": [s.model_dump() for s in result.segments]},
        total_duration_seconds=(result.total_duration_seconds),
        error_message=result.error,
        extracted_at=result.extracted_at,
    )
    session.add(db_result)


def _persist_extractor_error(
    session: Any,
    job_id: uuid.UUID,
    extractor_type: str,
    error_message: str,
) -> None:
    """Write a failed ExtractorResultModel to DB.
    Used to record permanent failures for observability.
    Commits immediately — separate from the main
    transaction that may have been rolled back.
    """

    try:
        db_result = ExtractorResultModel(
            job_id=job_id,
            extractor_type=extractor_type,
            segments_json={"segments": []},
            total_duration_seconds=0.0,
            error_message=error_message,
            extracted_at=datetime.now(UTC),
        )
        session.add(db_result)
        session.commit()
    except Exception as persist_exc:
        session.rollback()
        logger.critical(
            "Failed to persist extractor error state to DB. Error record is lost.",
            exc_info=persist_exc,
            extra={
                "job_id": str(job_id),
                "extractor_type": extractor_type,
                "original_error": error_message,
            },
        )
