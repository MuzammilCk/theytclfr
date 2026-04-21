"""Celery task for preflight video classification."""

import uuid
from typing import Any

from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.models.router_decision import RouterDecisionModel
from ytclfr.db.session import get_db
from ytclfr.ingestion.temp_storage import TempStorageManager
from ytclfr.queue.celery_app import celery_app
from ytclfr.router.audio_checker import check_audio_from_metadata
from ytclfr.router.classifier import classify
from ytclfr.router.frame_sampler import (
    FrameSamplerError,
    SampledFrames,
    sample_frames,
)
from ytclfr.router.metadata_inspector import inspect_metadata

logger = get_logger(__name__)


@celery_app.task(  # type: ignore
    bind=True,
    name="ytclfr.router.classify_video",
    queue="fast",
    max_retries=2,
    default_retry_delay=10,
)
def classify_video(
    self: Any, job_id: str
) -> dict[str, object]:
    """Classify a downloaded video using lightweight heuristics.

    Reads metadata from the database, samples frames via ffmpeg,
    checks audio presence, inspects keywords, and produces a
    RouterDecision stored back in the database.

    Args:
        job_id: String UUID of the job to classify.

    Returns:
        Dict with job_id, status, route, and confidence.
    """
    settings = get_settings()
    job_uuid = uuid.UUID(job_id)

    db_gen = get_db()
    session = next(db_gen)

    try:
        # Step 1-3: Load job
        job = session.query(Job).filter(Job.id == job_uuid).first()
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        # Step 4: Update status
        job.status = "classifying"
        session.commit()

        # Step 5: Check media path
        if job.local_media_path is None:
            job.status = "failed"
            job.error_message = (
                "No media path — download may have failed"
            )
            session.commit()
            return {
                "job_id": job_id,
                "status": "failed",
                "error": job.error_message,
            }

        # Step 6: Create frames directory
        from pathlib import Path

        temp_manager = TempStorageManager(settings)
        frames_dir = (
            temp_manager.get_job_dir(job_uuid) / "router_frames"
        )
        frames_dir.mkdir(parents=True, exist_ok=True)

        # Step 7: Sample frames
        try:
            sampled = sample_frames(
                video_path=Path(job.local_media_path),
                output_dir=frames_dir,
                sample_count=settings.router_frame_sample_count,
            )
        except FrameSamplerError as e:
            logger.warning(
                "Frame sampling failed for job %s: %s. "
                "Continuing with zero frames.",
                job_id,
                e,
            )
            sampled = SampledFrames(
                frame_paths=[],
                video_duration_seconds=(
                    job.duration_seconds
                    if job.duration_seconds
                    else 0.0
                ),
                sample_count=0,
            )

        # Step 8: Check audio from metadata
        audio_result = check_audio_from_metadata(
            job.metadata_raw or {}
        )

        # Step 9: Inspect metadata keywords
        meta_signals = inspect_metadata(job.metadata_raw or {})

        # Step 10: Classify
        decision = classify(
            job_id=job_uuid,
            audio=audio_result,
            metadata=meta_signals,
            frame_count=sampled.sample_count,
            video_duration_seconds=sampled.video_duration_seconds,
        )

        # Step 11: Persist RouterDecisionModel (upsert)
        existing = (
            session.query(RouterDecisionModel)
            .filter_by(job_id=job_uuid)
            .first()
        )
        if existing:
            existing.primary_route = decision.primary_route
            existing.confidence = decision.confidence
            existing.speech_density = decision.speech_density
            existing.ocr_density = decision.ocr_density
            existing.routing_notes = decision.routing_notes
            existing.decided_at = decision.decided_at
        else:
            db_decision = RouterDecisionModel(
                job_id=job_uuid,
                primary_route=decision.primary_route,
                confidence=decision.confidence,
                speech_density=decision.speech_density,
                ocr_density=decision.ocr_density,
                routing_notes=decision.routing_notes,
                decided_at=decision.decided_at,
            )
            session.add(db_decision)
        session.commit()

        # Step 12: Update job status
        job.status = "classified"
        session.commit()

        # Step 13: Log decision
        logger.info(
            "RouterDecision for job %s: route=%s confidence=%.2f",
            job_id,
            decision.primary_route,
            decision.confidence,
        )

        # Step 14: Return result
        return {
            "job_id": job_id,
            "status": "classified",
            "route": decision.primary_route,
            "confidence": decision.confidence,
        }

    except ValueError:
        # Non-retryable: job not found
        session.rollback()
        return {
            "job_id": job_id,
            "status": "failed",
            "error": f"Job not found: {job_id}",
        }

    except Exception as exc:
        # Retryable error
        session.rollback()
        try:
            job = (
                session.query(Job)
                .filter(Job.id == job_uuid)
                .first()
            )
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                session.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)

    finally:
        session.close()
