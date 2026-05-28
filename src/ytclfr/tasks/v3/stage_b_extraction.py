"""Celery task for V3 Stage B — Targeted Extraction.

Reads the SignalManifest produced by Stage A and dispatches a
dynamic Celery group containing only the extractors whose signals
were confirmed by probing.  The chord callback is
v3_run_evidence_fusion (V3 Stage C).

This task is idempotent: if the job is already in a post-Stage-B
status, it returns immediately without re-firing the chord.
"""

import json
from uuid import UUID

from ytclfr.contracts.events import StageBEvent, StageBStatus
from ytclfr.contracts.v3.manifest import SignalManifest
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.queue.celery_app import celery_app
from ytclfr.storage.manifest_store import SignalManifestStore

logger = get_logger(__name__)

# ── MODULE-LEVEL CONSTANTS ──────────────────────────────────────

# Minimum extractors: if no signal is detected, run this as
# a guaranteed fallback (uses metadata only, no S3 download)
FALLBACK_EXTRACTOR: str = "audio"

# Statuses that indicate Stage B has already run or a later
# stage is active — used for idempotency guard.
POST_STAGE_B_STATUSES: set[str] = {
    "extracting",
    "aligning",
    "aligned",
    "completed",
    "v3_stage_c_running",
    "v3_stage_c_complete",
    "v3_stage_d_running",
}

# ── MODULE-LEVEL SINGLETONS ─────────────────────────────────────

_manifest_store = SignalManifestStore()
_settings = get_settings()


def _build_extractor_names(manifest: SignalManifest) -> list[str]:
    """Return the list of extractor names to run for a manifest.

    Pure function — no Celery, no DB, no side effects.
    Used by v3_run_targeted_extraction and testable in isolation.

    Args:
        manifest: The SignalManifest produced by Stage A.

    Returns:
        List of extractor type strings, e.g. ["asr", "audio"].
        Always contains at least one item (fallback guarantee).
    """
    names: list[str] = []

    if manifest.has_speech:
        names.append("asr")

    # OCR fires on EITHER burned-in text OR structural detection
    if manifest.has_burned_in_text or manifest.ocr_required:
        names.append("ocr")

    if manifest.has_speech or manifest.has_music:
        names.append("audio")

    if not names:
        names.append(FALLBACK_EXTRACTOR)

    return names


from ytclfr.core.serialization import _sanitize_for_json


def _emit_sse(event: StageBEvent) -> None:
    """Publish a StageBEvent to the Redis SSE channel.

    Failure to emit is logged as WARNING but never raises —
    SSE emission is observability, not correctness.
    """
    try:
        import redis

        r = redis.Redis.from_url(_settings.redis_url)
        channel = f"job:{event.job_id}:events"
        payload = _sanitize_for_json(event.model_dump(mode="json"))
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
    name="ytclfr.tasks.v3.stage_b_extraction.v3_run_targeted_extraction",
    queue="fast",
    max_retries=2,
    default_retry_delay=30,
)
def v3_run_targeted_extraction(
    self: object, job_id: str
) -> dict[str, object]:
    """Read SignalManifest and dispatch only the required extractors.

    Stage B of the V3 evidence-based pipeline.  Reads the manifest
    produced by Stage A and builds a dynamic Celery group containing
    only the extractors whose signals were confirmed by probing.
    The chord callback fires v3_run_evidence_fusion (V3 Stage C).

    This task is idempotent: if the job is already in a post-Stage-B
    status (extracting, aligning, aligned, completed, v3_stage_c_*,
    v3_stage_d_*), it returns immediately without re-firing the
    extractor group.

    Args:
        job_id: String UUID of the job to process.

    Returns:
        Dict with job_id, status, and list of dispatched extractor names.
    """
    job_uuid = UUID(job_id)

    # Step 1 — Emit SSE STARTED event
    _emit_sse(
        StageBEvent(
            event_type=StageBStatus.STARTED,
            job_id=job_id,
        )
    )

    # Steps 2–9 wrapped in try/except for error handling
    try:
        # Step 2 — Open DB session.  Load Job record.
        with db_session() as session:
            job = (
                session.query(Job)
                .filter(Job.id == job_uuid)
                .first()
            )
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            # Step 3 — Idempotency check
            if job.status in POST_STAGE_B_STATUSES:
                logger.warning(
                    "V3 Stage B idempotency hit for job %s — "
                    "already in status %s, skipping",
                    job_id,
                    job.status,
                )
                return {
                    "job_id": job_id,
                    "status": "skipped",
                    "reason": (
                        f"job already in status {job.status}"
                    ),
                }

            # Step 4 — Update job status to v3_stage_b_running
            job.status = "v3_stage_b_running"
            session.commit()

            # Step 5 — Load SignalManifest from DB
            manifest = _manifest_store.get_by_job_id(
                session, job_uuid
            )
            if not manifest:
                raise ValueError(
                    f"SignalManifest not found for job {job_id}. "
                    "Stage A must complete before Stage B."
                )

            _emit_sse(
                StageBEvent(
                    event_type=StageBStatus.MANIFEST_LOADED,
                    job_id=job_id,
                    details={
                        "has_speech": manifest.has_speech,
                        "has_music": manifest.has_music,
                        "has_burned_in_text": (
                            manifest.has_burned_in_text
                        ),
                        "audio_type": manifest.audio_type,
                        "probing_confidence": (
                            manifest.probing_confidence
                        ),
                    },
                )
            )

            # Step 6 — Build dynamic extractor list
            # Lazy imports to avoid circular import issues
            from celery import chord, group  # noqa: E402

            from ytclfr.tasks.extract import (  # noqa: E402
                run_asr,
                run_audio_classifier,
                run_ocr,
            )

            dispatched_names = _build_extractor_names(manifest)

            # Map extractor names to Celery signatures
            # FIXME (BUG #2): V3 Stage B currently uses the V1/V2 ASR extractor (run_asr).
            # This means ASRCompletenessMetrics are never populated for V3.
            # A migration to extractors/v3_asr.py is planned for a future release.
            _name_to_sig = {
                "asr": run_asr.s(job_id),
                "ocr": run_ocr.s(job_id),
                "audio": run_audio_classifier.s(job_id),
            }
            tasks_to_run = [
                _name_to_sig[name] for name in dispatched_names
            ]

            _emit_sse(
                StageBEvent(
                    event_type=StageBStatus.GROUP_BUILT,
                    job_id=job_id,
                    extractors_dispatched=dispatched_names,
                    details={"group_size": len(tasks_to_run)},
                )
            )

            # Step 7 — Update job status and dispatch chord
            job.status = "extracting"
            session.commit()

            # V3 Stage C callback — chord fires v3_run_evidence_fusion
            # when all extractors complete.
            from ytclfr.tasks.v3.stage_c_fusion import (  # lazy import
                v3_run_evidence_fusion,
            )
            extractor_group = group(*tasks_to_run)
            chord(extractor_group)(v3_run_evidence_fusion.s(job_id))

            logger.info(
                "V3 Stage B dispatched %d extractor(s) for "
                "job %s: %s",
                len(tasks_to_run),
                job_id,
                dispatched_names,
            )

            # Step 8 — Emit SSE DISPATCHED
            _emit_sse(
                StageBEvent(
                    event_type=StageBStatus.DISPATCHED,
                    job_id=job_id,
                    extractors_dispatched=dispatched_names,
                    details={
                        "group_size": len(tasks_to_run)
                    },
                )
            )

            # Step 9 — Return
            return {
                "job_id": job_id,
                "status": "dispatched",
                "extractors": dispatched_names,
            }

    except Exception as exc:
        logger.error(
            "V3 Stage B failed for job %s: %s",
            job_id,
            exc,
            exc_info=True,
        )
        try:
            with db_session() as err_session:
                job_err = (
                    err_session.query(Job)
                    .filter(Job.id == job_uuid)
                    .first()
                )
                if job_err:
                    job_err.status = "v3_stage_b_failed"
                    job_err.error_message = str(exc)
                    err_session.commit()
        except Exception:
            pass

        _emit_sse(
            StageBEvent(
                event_type=StageBStatus.FAILED,
                job_id=job_id,
                error=str(exc),
            )
        )
        raise self.retry(exc=exc, countdown=30)  # type: ignore
