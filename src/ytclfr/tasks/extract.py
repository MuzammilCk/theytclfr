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

    Reads job.local_media_path from DB.
    Writes ExtractorResultModel to DB on completion.
    Returns serialized ExtractorResult dict.
    """

    job_uuid = uuid.UUID(job_id)

    with db_session() as session:
        try:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job or not job.local_media_path:
                raise ValueError(f"Job {job_id} not found or has no media path")

            from ytclfr.extractors.asr import (
                get_asr_extractor,
            )

            extractor = get_asr_extractor()
            result = extractor.extract(
                job_id=job_uuid,
                video_path=Path(job.local_media_path),
            )

            _persist_extractor_result(session, result)
            session.commit()

            logger.info(
                "ASR extraction complete for job %s: %d segments",
                job_id,
                len(result.segments),
            )
            return result.model_dump(mode="json")

        except Exception as exc:
            session.rollback()
            if self.request.retries >= self.max_retries:
                _persist_extractor_error(session, job_uuid, "asr", str(exc))
                logger.error(
                    "Extractor asr exhausted all retries for job %s: %s",
                    job_id,
                    str(exc),
                )
                return {
                    "job_id": job_id,
                    "extractor_type": "asr",
                    "error": str(exc),
                    "segments": [],
                    "total_duration_seconds": 0.0,
                    "extracted_at": datetime.now(UTC).isoformat(),
                }
            raise self.retry(exc=exc)


@celery_app.task(  # type: ignore
    bind=True,
    base=BaseExtractorTask,
    name="ytclfr.extract.run_ocr",
    queue="heavy",
)
def run_ocr(self: Any, job_id: str) -> dict[str, object]:
    """Run OCR frame extraction on the downloaded video.

    Creates an ocr_frames subdirectory inside the job's
    temp directory. Writes ExtractorResultModel to DB.
    Returns serialized ExtractorResult dict.
    """
    settings = get_settings()
    job_uuid = uuid.UUID(job_id)

    with db_session() as session:
        try:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job or not job.local_media_path:
                raise ValueError(f"Job {job_id} not found or has no media path")

            from ytclfr.ingestion.temp_storage import (
                TempStorageManager,
            )

            temp_manager = TempStorageManager(settings)
            ocr_frames_dir = temp_manager.get_job_dir(job_uuid) / "ocr_frames"

            from ytclfr.extractors.ocr import (
                get_ocr_extractor,
            )

            extractor = get_ocr_extractor()
            result = extractor.extract(
                job_id=job_uuid,
                video_path=Path(job.local_media_path),
                output_dir=ocr_frames_dir,
            )

            _persist_extractor_result(session, result)
            session.commit()

            logger.info(
                "OCR extraction complete for job %s: %d segments",
                job_id,
                len(result.segments),
            )
            return result.model_dump(mode="json")

        except Exception as exc:
            session.rollback()
            if self.request.retries >= self.max_retries:
                _persist_extractor_error(session, job_uuid, "ocr", str(exc))
                logger.error(
                    "Extractor ocr exhausted all retries for job %s: %s",
                    job_id,
                    str(exc),
                )
                return {
                    "job_id": job_id,
                    "extractor_type": "ocr",
                    "error": str(exc),
                    "segments": [],
                    "total_duration_seconds": 0.0,
                    "extracted_at": datetime.now(UTC).isoformat(),
                }
            raise self.retry(exc=exc)


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
    """
    job_uuid = uuid.UUID(job_id)

    with db_session() as session:
        try:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")

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
            return result.model_dump(mode="json")

        except Exception as exc:
            session.rollback()
            if self.request.retries >= self.max_retries:
                _persist_extractor_error(session, job_uuid, "audio", str(exc))
                logger.error(
                    "Extractor audio exhausted all retries for job %s: %s",
                    job_id,
                    str(exc),
                )
                return {
                    "job_id": job_id,
                    "extractor_type": "audio",
                    "error": str(exc),
                    "segments": [],
                    "total_duration_seconds": 0.0,
                    "extracted_at": datetime.now(UTC).isoformat(),
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
