"""Celery task for Stage C — Evidence Fusion.

run_fuse_evidence is the chord callback that replaces
build_timeline for jobs processed by the V2 pipeline.
It is the direct equivalent of build_timeline but adds
entity extraction, Groq semantic reasoning, and
EvidenceGraph persistence.

build_timeline (tasks/align.py) is NOT deleted or modified.
It remains the callback for the V1 path (classify_video).
"""

import json
from collections import defaultdict
from uuid import UUID

from sqlalchemy.sql import func

from ytclfr.contracts.events import StageCEvent, StageCStatus
from ytclfr.contracts.evidence import (
    EvidenceGraph,
    ExtractedEntity,
    FusedSegment,
)
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.queue.celery_app import celery_app
from ytclfr.storage.evidence_store import EvidenceGraphStore

logger = get_logger(__name__)

# ── MODULE-LEVEL CONSTANTS ──────────────────────────────────

# Minimum confidence for the EvidenceGraph based on
# alignment engine output
MIN_CONFIDENCE_THRESHOLD: float = 0.0

# ── MODULE-LEVEL SINGLETONS ─────────────────────────────────

_evidence_store = EvidenceGraphStore()
_settings = get_settings()

def _emit_sse(event: StageCEvent) -> None:
    """Publish a StageCEvent to Redis SSE channel.
    Failure logs WARNING but never raises."""
    try:
        import redis

        r = redis.Redis.from_url(_settings.redis_url)
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

@celery_app.task(
    bind=True,
    name="ytclfr.tasks.stage_c.run_fuse_evidence",
    queue="fast",
    max_retries=2,
    default_retry_delay=30,
)
def run_fuse_evidence(
    self,
    extractor_results: list[dict],
    job_id: str,
) -> dict[str, object]:
    """Chord callback: fuse extracted evidence into EvidenceGraph.

    Replaces build_timeline as the V2 chord callback.
    Receives lightweight status dicts from the extractor group
    (identical to build_timeline's first argument).

    Args:
        extractor_results: Lightweight dicts from the Celery
            chord group [{job_id, extractor_type, status}, ...].
            Full results are fetched from the DB.
        job_id: String UUID of the job being processed.

    Returns:
        Dict with job_id, status, and EvidenceGraph summary.
    """
    job_uuid = UUID(job_id)

    # Step 1 — Log chord results and emit STARTED SSE
    for er in extractor_results:
        logger.info(
            "Stage C chord result for job %s: "
            "type=%s status=%s",
            job_id,
            er.get("extractor_type", "unknown"),
            er.get("status", "unknown"),
        )
    _emit_sse(StageCEvent(
        event_type=StageCStatus.STARTED,
        job_id=job_id,
        details={"extractor_count": len(extractor_results)},
    ))

    try:
        # Step 2 — Load settings and set job status to stage_c_running
        settings = get_settings()
        with db_session() as session:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            job.status = "stage_c_running"
            session.commit()

        # Step 3 — Fetch full extractor results from DB
        from ytclfr.tasks.align import _fetch_extractor_results_from_db
        db_extractor_results = _fetch_extractor_results_from_db(job_uuid)

        # Step 4 — Run V1 alignment engine (backward compatibility)
        from ytclfr.alignment.engine import align
        from ytclfr.confidence.controller import evaluate
        from ytclfr.storage.segment_store import save_aligned_segments

        timeline = align(job_id=job_uuid, extractor_results=db_extractor_results)

        verdict = evaluate(
            extractor_results=db_extractor_results,
            aligned_timeline_dict=timeline.model_dump(mode="json"),
            current_attempt=0,
        )

        with db_session() as session:
            save_aligned_segments(job_uuid, timeline, settings, session)

        logger.info(
            "Stage C alignment done for job %s: "
            "%d segments, confidence=%.2f",
            job_id, timeline.total_segments,
            verdict.aggregate_score.overall,
        )

        _emit_sse(StageCEvent(
            event_type=StageCStatus.ALIGNMENT_COMPLETE,
            job_id=job_id,
            details={
                "total_segments": timeline.total_segments,
                "has_gaps": timeline.has_gaps,
                "confidence": verdict.aggregate_score.overall,
            },
        ))

        # Step 5 — Entity extraction
        from ytclfr.fusion.entity_extractor import extract_entities_from_timeline

        heuristic_entities = extract_entities_from_timeline(
            list(timeline.segments)
        )

        _emit_sse(StageCEvent(
            event_type=StageCStatus.ENTITIES_EXTRACTED,
            job_id=job_id,
            details={"entity_count": len(heuristic_entities)},
        ))

        # Step 6 — Groq semantic reasoning
        from ytclfr.fusion.groq_reasoner import reason_over_evidence

        groq_result = reason_over_evidence(
            segments=list(timeline.segments),
            entity_hints=heuristic_entities,
            settings=settings,
        )

        if groq_result.reasoning_used:
            _emit_sse(StageCEvent(
                event_type=StageCStatus.GROQ_COMPLETE,
                job_id=job_id,
                details={
                    "dominant_subject": groq_result.dominant_subject,
                    "entity_count": len(groq_result.refined_entities),
                    "scene_boundaries": len(groq_result.scene_boundaries),
                },
            ))
        else:
            _emit_sse(StageCEvent(
                event_type=StageCStatus.GROQ_SKIPPED,
                job_id=job_id,
            ))

        # Step 7 — Build final entity list
        if groq_result.reasoning_used and groq_result.refined_entities:
            final_entities = []
            for e in groq_result.refined_entities:
                valid_types = {
                    "product", "person", "place", "topic", "unknown"
                }
                etype = e.get("type", "unknown")
                if etype not in valid_types:
                    etype = "unknown"
                final_entities.append(ExtractedEntity(
                    name=e["name"],
                    entity_type=etype,
                    mentioned_at=e.get("timestamps", [])[:10],
                    confidence=0.85,
                ))
        else:
            final_entities = heuristic_entities

        # Step 8 — Build FusedSegment list
        fused_segments = []
        entity_names_at = defaultdict(set)
        for entity in final_entities:
            for ts in entity.mentioned_at:
                entity_names_at[ts].add(entity.name)

        for seg in timeline.segments:
            fused_segments.append(FusedSegment(
                timestamp=seg.timestamp,
                end_timestamp=seg.end_timestamp,
                text=seg.text,
                source=seg.source,
                confidence=seg.confidence,
                entity_refs=list(entity_names_at.get(seg.timestamp, set())),
            ))

        # Step 9 — Build and persist EvidenceGraph
        graph = EvidenceGraph(
            job_id=job_uuid,
            segments=fused_segments,
            entities=final_entities,
            dominant_subject=groq_result.dominant_subject,
            groq_summary=groq_result.summary,
            scene_boundaries=groq_result.scene_boundaries,
            groq_reasoning_used=groq_result.reasoning_used,
            total_segments=len(fused_segments),
            confidence=round(verdict.aggregate_score.overall, 3),
        )

        with db_session() as session:
            orm_graph = _evidence_store.upsert(session, graph)

        # Step 10 — Update job status to stage_c_complete
        with db_session() as session:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if job:
                job.status = "stage_c_complete"
                job.updated_at = func.now()
                session.commit()

        # Step 11 — Clean up S3 video directory
        from ytclfr.ingestion.s3_storage import (
            S3StorageError,
            S3StorageManager,
        )
        try:
            s3_manager = S3StorageManager(settings)
            s3_manager.delete_directory(prefix=f"{job_id}/")
        except (S3StorageError, AttributeError) as exc:
            logger.warning(
                "Failed to delete S3 directory for job %s: %s",
                job_id, exc,
            )

        # Step 12 — Emit COMPLETE SSE
        _emit_sse(StageCEvent(
            event_type=StageCStatus.COMPLETE,
            job_id=job_id,
            evidence_graph_id=str(orm_graph.id),
            details={
                "total_segments": graph.total_segments,
                "entity_count": len(graph.entities),
                "groq_used": graph.groq_reasoning_used,
                "dominant_subject": graph.dominant_subject,
            },
        ))

        # Step 13 — Stage D trigger — dispatch taxonomy mapping
        from ytclfr.tasks.stage_d import run_taxonomy_mapping  # lazy
        run_taxonomy_mapping.delay(job_id)
        logger.info(
            "Stage D triggered for job %s", job_id
        )

        return {
            "job_id": job_id,
            "status": "evidence_fused",
            "total_segments": graph.total_segments,
            "entity_count": len(graph.entities),
            "groq_reasoning_used": graph.groq_reasoning_used,
        }

    except Exception as exc:
        logger.error(
            "Stage C failed for job %s: %s",
            job_id, exc, exc_info=True,
        )
        try:
            with db_session() as err_session:
                job_err = err_session.query(Job).filter(
                    Job.id == job_uuid
                ).first()
                if job_err:
                    job_err.status = "stage_c_failed"
                    job_err.error_message = str(exc)
                    err_session.commit()
        except Exception:
            pass

        _emit_sse(StageCEvent(
            event_type=StageCStatus.FAILED,
            job_id=job_id,
            error=str(exc),
        ))
        raise self.retry(exc=exc, countdown=30)
