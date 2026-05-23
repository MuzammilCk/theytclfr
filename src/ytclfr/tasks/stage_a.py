"""Celery task for Stage A — Signal Census.

Orchestrates audio, visual, and metadata probing. Produces and
persists a SignalManifest for the given job. Emits SSE events at
start, per-probe completion, and on finish.

This task is idempotent: if a manifest already exists for this
job_id, it overwrites it.
"""

import json
import logging
import os
from uuid import UUID

from ytclfr.contracts.events import StageAEvent, StageAStatus
from ytclfr.contracts.manifest import SignalManifest
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.probing.audio_checker import probe_audio
from ytclfr.probing.frame_sampler import probe_visual
from ytclfr.probing.metadata_probe import probe_metadata
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

            # Step 4 — Resolve file paths
            video_path = job.local_media_path
            if not video_path:
                raise ValueError(
                    f"No local media path for job: {job_id}"
                )

            # Derive audio path — try sidecar formats
            base_path = os.path.splitext(video_path)[0]
            audio_path = video_path  # default: probe from video
            for ext in (".m4a", ".webm", ".mp4"):
                candidate = base_path + ext
                if os.path.exists(candidate):
                    audio_path = candidate
                    break

            # Derive metadata JSON path
            metadata_json_path = base_path + ".info.json"

            # Step 5 — Run probe_metadata (cheapest)
            metadata_result = None
            try:
                metadata_result = probe_metadata(
                    metadata_json_path
                )
                _emit_sse(
                    StageAEvent(
                        event_type=StageAStatus.PROBE_METADATA_COMPLETE,
                        job_id=job_id,
                    )
                )
            except (FileNotFoundError, ValueError) as exc:
                logger.warning(
                    "Metadata probe failed for job %s: %s",
                    job_id,
                    exc,
                )
                metadata_result = None

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
                        "has_speech": audio_result.has_speech,
                        "has_music": audio_result.has_music,
                    },
                )
            )

            # Step 7 — Run probe_visual (slowest)
            visual_result = probe_visual(video_path)
            _emit_sse(
                StageAEvent(
                    event_type=StageAStatus.PROBE_VISUAL_COMPLETE,
                    job_id=job_id,
                    details={
                        "motion_score": visual_result.motion_score,
                        "has_faces": visual_result.has_faces,
                        "scene_cuts": visual_result.scene_cut_count,
                    },
                )
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

            # STAGE-B-TODO: trigger run_targeted_extraction.delay(job_id)
            # here once tasks/stage_b.py is built and confirmed stable.

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
