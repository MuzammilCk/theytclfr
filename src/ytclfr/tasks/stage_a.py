"""Celery task for Stage A — Signal Census.

Orchestrates audio, visual, and metadata probing. Produces and
persists a SignalManifest for the given job. Emits SSE events at
start, per-probe completion, and on finish.

This task is idempotent: if a manifest already exists for this
job_id, it overwrites it.
"""

import json
import logging  # noqa: F401
import os
from pathlib import Path
from uuid import UUID

from ytclfr.contracts.events import StageAEvent, StageAStatus
from ytclfr.contracts.manifest import SignalManifest
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.ingestion.s3_storage import S3StorageManager
from ytclfr.ingestion.temp_storage import TempStorageManager
from ytclfr.probing.audio_checker import probe_audio
from ytclfr.probing.frame_sampler import probe_visual
from ytclfr.probing.metadata_probe import (
    probe_metadata,  # noqa: F401
    probe_metadata_dict,
)
from ytclfr.probing.structural_detector import probe_structural
from ytclfr.queue.celery_app import celery_app
from ytclfr.storage.manifest_store import SignalManifestStore

logger = get_logger(__name__)

# Singleton store instance
_manifest_store = SignalManifestStore()



def _emit_sse(event: StageAEvent) -> None:
    """Publish an SSE event to Redis pub/sub.

    If the emit fails, log a WARNING but do not crash the task.
    """
    try:
        import redis

        settings = get_settings()
        r = redis.Redis.from_url(settings.redis_url)
        channel = f"job:{event.job_id}:events"
        payload = event.model_dump(mode="json")
        r.publish(channel, json.dumps(payload))
        logger.debug(
            "SSE event published: %s for job %s",
            event.event_type,
            event.job_id,
        )
    except Exception as exc:
        logger.warning(
            "Failed to emit SSE event %s for job %s: %s",
            event.event_type,
            event.job_id,
            exc,
        )


@celery_app.task(  # type: ignore
    bind=True,
    name="ytclfr.tasks.stage_a.run_signal_census",
    queue="heavy",
    max_retries=2,
    default_retry_delay=30,
)
def run_signal_census(
    self: object, job_id: str
) -> dict[str, object]:
    """Orchestrate Stage A: probe audio, visual, and metadata signals.

    Produces and persists a SignalManifest for the given job.
    Emits SSE events at start, per-probe completion, and on finish.
    This task is idempotent: if a manifest already exists for this
    job_id, it overwrites it.

    Args:
        job_id: String UUID of the job to probe.

    Returns:
        Dict with status, job_id, and serialised manifest.
    """
    # Step 1 — Emit STARTED event
    _emit_sse(
        StageAEvent(
            event_type=StageAStatus.STARTED,
            job_id=job_id,
        )
    )

    # Step 2 — Load settings and open DB session
    settings = get_settings()
    with db_session() as session:
        local_video_path: Path | None = None
        is_transient_download: bool = False
        try:
            # Step 3 — Fetch job record
            job = (
                session.query(Job)
                .filter(Job.id == UUID(job_id))
                .first()
            )
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            job.status = "stage_a_running"
            session.commit()

            # Step 4 — Resolve media path (local or S3)
            # Phase 10: after ingestion the video is in S3 and
            # job.local_media_path is None on extraction workers.
            # Download to a transient scratch path and clean up in finally.
            if job.local_media_path and os.path.exists(job.local_media_path):
                # Local path still exists (e.g. same node, pre-Phase-10 path)
                video_path = job.local_media_path
            else:
                # Video is in S3 — download transiently for probing
                if not job.s3_video_uri:
                    raise ValueError(
                        f"No media available for job {job_id}: "
                        "local_media_path is None and s3_video_uri is None. "
                        "Ingestion may have failed."
                    )
                s3_manager = S3StorageManager(settings)
                temp_manager = TempStorageManager(settings)
                local_dir = temp_manager.get_job_dir(UUID(job_id))
                local_video_path = local_dir / "video_probe.mp4"
                s3_object_key = f"{job_id}/video.mp4"
                s3_manager.download_file(s3_object_key, local_video_path)
                video_path = str(local_video_path)
                is_transient_download = True
                logger.info(
                    "Downloaded video from S3 for probing: job=%s path=%s",
                    job_id,
                    local_video_path,
                )

            # Derive audio path from the resolved video path
            base_path = os.path.splitext(video_path)[0]
            audio_path = video_path  # default: probe audio from video container
            for ext in (".m4a", ".webm"):
                candidate = base_path + ext
                if os.path.exists(candidate):
                    audio_path = candidate
                    break

            # Step 5 — Run probe_metadata_dict from job.metadata_raw
            # Uses the yt-dlp dict already stored in PostgreSQL.
            # No .info.json file is ever written to disk (DR-V2-02).
            metadata_result = None
            if job.metadata_raw and isinstance(job.metadata_raw, dict):
                try:
                    metadata_result = probe_metadata_dict(job.metadata_raw)
                    _emit_sse(
                        StageAEvent(
                            event_type=StageAStatus.PROBE_METADATA_COMPLETE,
                            job_id=job_id,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "Metadata dict probe failed for job %s: %s",
                        job_id,
                        exc,
                    )
                    metadata_result = None
            else:
                logger.warning(
                    "job.metadata_raw is empty or non-dict for job %s — "
                    "metadata probe skipped",
                    job_id,
                )

            # Step 6 — Run probe_audio
            metadata_dict = (
                metadata_result.__dict__
                if metadata_result
                else None
            )
            audio_result = probe_audio(
                audio_path, metadata=metadata_dict
            )
            _emit_sse(
                StageAEvent(
                    event_type=StageAStatus.PROBE_AUDIO_COMPLETE,
                    job_id=job_id,
                    details={
                        "audio_type": audio_result.audio_type,
                        "has_speech": bool(audio_result.has_speech),
                        "has_music": bool(audio_result.has_music),
                    },
                )
            )

            # Step 7 — Run probe_visual (slowest)
            visual_result = probe_visual(video_path, retain_frames=True)
            _emit_sse(
                StageAEvent(
                    event_type=StageAStatus.PROBE_VISUAL_COMPLETE,
                    job_id=job_id,
                    details={
                        "motion_score": float(visual_result.motion_score),
                        "has_faces": bool(visual_result.has_faces),
                        "scene_cuts": int(visual_result.scene_cut_count),
                    },
                )
            )

            # Step 7.5a — Compute metadata prior for structural corroboration
            metadata_prior = 0.5
            if metadata_result and metadata_result.metadata_structural_hints:
                hints = metadata_result.metadata_structural_hints
                if hints.get("title_has_ordinals") or hints.get("title_has_list_keywords"):
                    metadata_prior = 0.7

            # Step 7.5b — Run probe_structural with metadata corroboration
            structural_result = probe_structural(
                sampled_frames=visual_result.sampled_frames,
                visual_cut_count=visual_result.scene_cut_count,
                visual_motion_density=visual_result.motion_density,
                has_speech=audio_result.has_speech,
                has_music=audio_result.has_music,
                metadata_prior_confidence=metadata_prior,
            )

            # Step 8 — Merge into SignalManifest
            manifest = SignalManifest(
                job_id=UUID(job_id),
                audio_type=audio_result.audio_type,
                language=(
                    (
                        metadata_result.language
                        if metadata_result
                        else None
                    )
                    or audio_result.language
                ),
                has_speech=audio_result.has_speech,
                has_music=audio_result.has_music,
                has_burned_in_text=(
                    visual_result.has_burned_in_text
                ),
                has_subtitle_track=(
                    metadata_result.has_subtitle_track
                    if metadata_result
                    else False
                ),
                has_faces=visual_result.has_faces,
                motion_density=visual_result.motion_density,
                motion_score=visual_result.motion_score,
                aspect_ratio=(
                    metadata_result.aspect_ratio
                    if metadata_result
                    and metadata_result.aspect_ratio != "unknown"
                    else visual_result.aspect_ratio
                ),
                content_format=visual_result.content_format,
                scene_cut_count=visual_result.scene_cut_count,
                duration_seconds=(
                    (
                        metadata_result.duration_seconds
                        if metadata_result
                        else None
                    )
                    or audio_result.duration_seconds
                ),
                metadata_prior_confidence=metadata_prior,
                structural_score=structural_result.structural_score,
                list_likelihood=structural_result.list_likelihood,
                countdown_likelihood=structural_result.countdown_likelihood,
                overlay_text_density=structural_result.overlay_text_density,
                ordinal_pattern_score=structural_result.ordinal_pattern_score,
                scene_repeat_score=structural_result.scene_repeat_score,
                ocr_required=structural_result.ocr_required,
                ocr_expected_coverage=structural_result.ocr_expected_coverage,
                asr_expected_value=structural_result.asr_expected_value,
                structural_video_type=structural_result.structural_video_type,
                probing_confidence=round(
                    (
                        audio_result.confidence
                        + visual_result.confidence
                        + (
                            metadata_result.confidence
                            if metadata_result
                            else 0.5
                        )
                    )
                    / 3.0,
                    3,
                ),
            )

            # Step 9 — Persist manifest
            orm_manifest = _manifest_store.create(
                session, manifest
            )

            # Update job status
            job.status = "stage_a_complete"
            session.commit()

            # Step 10 — Emit COMPLETE event
            _emit_sse(
                StageAEvent(
                    event_type=StageAStatus.COMPLETE,
                    job_id=job_id,
                    manifest_id=str(orm_manifest.id),
                )
            )

            # Stage B trigger — dispatch targeted extraction
            from ytclfr.tasks.stage_b import run_targeted_extraction
            run_targeted_extraction.delay(job_id)
            logger.info(
                "Stage B triggered for job %s", job_id
            )

            # Step 12 — Return
            return {
                "status": "ok",
                "job_id": job_id,
                "manifest": manifest.model_dump(mode="json"),
            }

        except Exception as exc:
            logger.error(
                "Stage A failed for job %s: %s",
                job_id,
                exc,
                exc_info=True,
            )
            try:
                job = (
                    session.query(Job)
                    .filter(Job.id == UUID(job_id))
                    .first()
                )
                if job:
                    job.status = "stage_a_failed"
                    job.error_message = str(exc)
                    session.commit()
            except Exception:
                session.rollback()

            _emit_sse(
                StageAEvent(
                    event_type=StageAStatus.FAILED,
                    job_id=job_id,
                    error=str(exc),
                )
            )
            raise self.retry(exc=exc, countdown=30)  # type: ignore
        finally:
            # Clean up transient S3 download to keep node stateless.
            # Uses unlink() on the specific file only — not cleanup_job()
            # which causes race conditions (Phase 10 bugfix pattern).
            if (
                is_transient_download
                and local_video_path is not None
                and local_video_path.exists()
            ):
                try:
                    local_video_path.unlink(missing_ok=True)
                    logger.debug(
                        "Cleaned up transient probe file for job %s",
                        job_id,
                    )
                except Exception as cleanup_exc:
                    logger.warning(
                        "Failed to clean up transient probe file "
                        "%s for job %s: %s",
                        local_video_path,
                        job_id,
                        cleanup_exc,
                    )
