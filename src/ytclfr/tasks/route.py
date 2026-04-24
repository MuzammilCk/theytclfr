"""Celery task for preflight video classification."""

import uuid
from pathlib import Path
from typing import Any

from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.models.router_decision import RouterDecisionModel
from ytclfr.db.session import db_session
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
def classify_video(self: Any, job_id: str) -> dict[str, object]:
    """Classify a downloaded video using lightweight heuristics.

    Phase 10: Downloads the video from S3 to a transient local path
    for frame sampling, then deletes it in the finally block.

    Args:
        job_id: String UUID of the job to classify.

    Returns:
        Dict with job_id, status, route, and confidence.
    """
    settings = get_settings()
    job_uuid = uuid.UUID(job_id)
    local_video_path: Path | None = None

    with db_session() as session:
        try:
            # Step 1-3: Load job
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            # Step 4: Update status
            job.status = "classifying"
            session.commit()

            # Step 5: Download video from S3 for frame sampling
            if not job.s3_video_uri:
                job.status = "failed"
                job.error_message = "No S3 video URI — upload may have failed"
                session.commit()
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "error": job.error_message,
                }

            from ytclfr.ingestion.s3_storage import S3StorageManager

            s3_manager = S3StorageManager(settings)
            temp_manager = TempStorageManager(settings)
            local_dir = temp_manager.get_job_dir(job_uuid)
            local_video_path = local_dir / "video.mp4"

            s3_object_key = f"{job_id}/video.mp4"
            s3_manager.download_file(s3_object_key, local_video_path)

            # Step 6: Create frames directory
            frames_dir = local_dir / "router_frames"
            frames_dir.mkdir(parents=True, exist_ok=True)

            # Step 7: Sample frames
            try:
                sampled = sample_frames(
                    video_path=local_video_path,
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
                        job.duration_seconds if job.duration_seconds else 0.0
                    ),
                    sample_count=0,
                )

            # Step 8: Check audio from metadata
            meta_dict = job.metadata_raw if isinstance(job.metadata_raw, dict) else {}
            audio_result = check_audio_from_metadata(meta_dict)

            # Step 9: Inspect metadata keywords
            meta_signals = inspect_metadata(meta_dict)

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
                session.query(RouterDecisionModel).filter_by(job_id=job_uuid).first()
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
            # Dispatch extractors in parallel after classification.
            # ASR and OCR run as a Celery group (parallel).
            # Audio classifier runs on the fast queue.
            # All three complete before build_timeline callback runs.
            from celery import chord, group

            from ytclfr.tasks.align import build_timeline
            from ytclfr.tasks.extract import (
                run_asr,
                run_audio_classifier,
                run_ocr,
            )

            extractor_group = group(
                run_asr.s(job_id),
                run_ocr.s(job_id),
                run_audio_classifier.s(job_id),
            )
            chord(extractor_group)(build_timeline.s(job_id))

            # Update job status to "extracting"
            job.status = "extracting"
            session.commit()

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
                job = session.query(Job).filter(Job.id == job_uuid).first()
                if job:
                    job.status = "failed"
                    job.error_message = str(exc)
                    session.commit()
            except Exception:
                pass
            raise self.retry(exc=exc)

        finally:
            # Phase 10 Bugfix: Only delete the specific files this task created.
            # DO NOT use cleanup_job() as it causes race conditions with parallel extractors.
            if local_video_path and local_video_path.exists():
                try:
                    local_video_path.unlink(missing_ok=True)
                except Exception as cleanup_exc:
                    logger.warning("Failed to clean up local file %s: %s", local_video_path, cleanup_exc)
            
            if 'frames_dir' in locals() and frames_dir.exists():
                import shutil
                shutil.rmtree(frames_dir, ignore_errors=True)
