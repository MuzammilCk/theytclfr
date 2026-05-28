"""Celery task for V3 Stage D — Taxonomy + Intent Mapping.

v3_run_taxonomy_mapping is the terminal V3 pipeline task.
It reads the V3 EvidenceGraph, classifies taxonomy
(Groq + rule-based fallback), and persists a V3 FinalResponse
to the final_outputs table with content_type="v3_...".

After this task, job.status = "completed".
"""

import json
from uuid import UUID

from ytclfr.contracts.events import StageDEvent, StageDStatus
from ytclfr.contracts.v3.response import (
    ExtractedItem,
    FinalResponse,
    TaxonomyResult,
)
from ytclfr.contracts.v3.evidence import (
    EvidenceGraph,
    ExtractedEntity,
    FusedSegment,
)
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM
from ytclfr.db.session import db_session
from ytclfr.queue.celery_app import celery_app

logger = get_logger(__name__)

# ── MODULE-LEVEL CONSTANTS ──────────────────────────────────

V3_CONTENT_TYPE_PREFIX: str = "v3_"
MAX_EVIDENCE_SUMMARY_SEGMENTS: int = 20


# ── SSE HELPER ──────────────────────────────────────────────

def _sanitize_for_json(obj):
    """Recursively convert numpy scalars to native Python types."""
    try:
        import numpy as np
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def _emit_sse(event: StageDEvent) -> None:
    """Publish a StageDEvent to Redis SSE channel."""
    settings = get_settings()
    channel = f"job:{event.job_id}:events"
    try:
        import redis
        r = redis.Redis.from_url(settings.redis_url)
        payload = _sanitize_for_json(event.model_dump(mode="json"))
        r.publish(channel, json.dumps(payload))
        logger.info("SSE emitted to %s: %s", channel, event.event_type)
    except Exception as exc:
        logger.warning(
            "Failed to emit SSE event %s: %s",
            event.event_type, exc
        )


def _load_v3_evidence_graph(session, job_uuid: UUID) -> EvidenceGraph | None:
    """Load V3 EvidenceGraph from v3_evidence_graphs table."""
    orm = session.query(V3EvidenceGraphORM).filter(
        V3EvidenceGraphORM.job_id == job_uuid
    ).first()
    if not orm:
        return None

    # Reconstruct from JSON columns
    segments_raw = orm.segments_json.get("segments", []) if isinstance(orm.segments_json, dict) else []
    entities_raw = orm.entities_json.get("entities", []) if isinstance(orm.entities_json, dict) else []
    boundaries_raw = orm.scene_boundaries_json.get("boundaries", []) if isinstance(orm.scene_boundaries_json, dict) else []
    coverage = orm.modality_coverage_json if isinstance(orm.modality_coverage_json, dict) else {}
    conflicts_raw = orm.conflict_details_json.get("details", []) if isinstance(orm.conflict_details_json, dict) else []
    notes_raw = orm.evidence_priority_notes_json.get("notes", []) if isinstance(orm.evidence_priority_notes_json, dict) else []

    segments = [FusedSegment.model_validate(s) for s in segments_raw]
    entities = [ExtractedEntity.model_validate(e) for e in entities_raw]

    return EvidenceGraph(
        job_id=orm.job_id,
        segments=segments,
        entities=entities,
        dominant_subject=orm.dominant_subject,
        groq_summary=orm.groq_summary,
        scene_boundaries=boundaries_raw,
        groq_reasoning_used=orm.groq_reasoning_used,
        modality_coverage=coverage,
        conflict_count=orm.conflict_count,
        conflict_details=conflicts_raw,
        structural_video_type=orm.structural_video_type,
        evidence_priority_notes=notes_raw,
        primary_evidence_modality=orm.primary_evidence_modality,
        total_segments=orm.total_segments,
        confidence=orm.confidence,
    )


# ── TASK DEFINITION ─────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="ytclfr.tasks.v3.stage_d_taxonomy.v3_run_taxonomy_mapping",
    queue="fast",
    max_retries=2,
    default_retry_delay=30,
)
def v3_run_taxonomy_mapping(
    self,
    job_id: str,
) -> dict[str, object]:
    """Read V3 EvidenceGraph and produce V3 FinalResponse with taxonomy.

    Terminal task of the V3 pipeline. Sets job.status = "completed".
    """
    job_uuid = UUID(job_id)

    try:
        # Step 1 — Emit STARTED
        _emit_sse(StageDEvent(
            event_type=StageDStatus.STARTED,
            job_id=job_id,
        ))

        # Step 2 — Set job status, load manifest for context
        settings = get_settings()
        with db_session() as session:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            job.status = "v3_stage_d_running"
            session.commit()

            signal_manifest_has_speech = True
            signal_manifest_has_music = False
            from ytclfr.storage.manifest_store import SignalManifestStore
            manifest_store = SignalManifestStore()
            manifest = manifest_store.get_by_job_id(session, job_uuid)
            if manifest:
                signal_manifest_has_speech = manifest.has_speech
                signal_manifest_has_music = manifest.has_music

            # Step 3 — Idempotency check
            from ytclfr.db.models.final_output import FinalOutputModel
            existing = session.query(FinalOutputModel).filter(
                FinalOutputModel.job_id == job_uuid,
            ).first()
            if existing and existing.content_type.startswith(V3_CONTENT_TYPE_PREFIX):
                logger.warning(
                    "V3 Stage D idempotency hit for job %s — "
                    "V3 FinalResponse already exists, skipping",
                    job_id,
                )
                return {
                    "job_id": job_id,
                    "status": "skipped",
                    "reason": "V3 FinalResponse already persisted",
                }

        # Step 4 — Load V3 EvidenceGraph from v3_evidence_graphs table
        with db_session() as session:
            evidence_graph = _load_v3_evidence_graph(session, job_uuid)
        if not evidence_graph:
            raise ValueError(
                f"V3 EvidenceGraph not found for job {job_id}. "
                "V3 Stage C must complete before Stage D."
            )

        _emit_sse(StageDEvent(
            event_type=StageDStatus.EVIDENCE_LOADED,
            job_id=job_id,
            details={
                "total_segments": evidence_graph.total_segments,
                "entity_count": len(evidence_graph.entities),
                "dominant_subject": evidence_graph.dominant_subject,
                "groq_reasoning_was_used": evidence_graph.groq_reasoning_used,
            },
        ))

        # Step 5 — Taxonomy classification (reused, version-agnostic)
        from ytclfr.taxonomy.mapper import MAX_ENTITIES_IN_PROMPT, classify_taxonomy

        entity_dicts = [
            {"name": e.name, "type": e.entity_type}
            for e in evidence_graph.entities[:MAX_ENTITIES_IN_PROMPT]
        ]

        groq_taxonomy = classify_taxonomy(
            dominant_subject=evidence_graph.dominant_subject,
            groq_summary=evidence_graph.groq_summary,
            entities=entity_dicts,
            has_speech=signal_manifest_has_speech,
            has_music=signal_manifest_has_music,
            settings=settings,
            structural_video_type=evidence_graph.structural_video_type,
        )

        if groq_taxonomy.groq_used:
            _emit_sse(StageDEvent(
                event_type=StageDStatus.GROQ_TAXONOMY_COMPLETE,
                job_id=job_id,
                taxonomy={
                    "parent": groq_taxonomy.parent_category,
                    "child": groq_taxonomy.child_category,
                    "intent": groq_taxonomy.intent,
                },
                details={"confidence": groq_taxonomy.confidence},
            ))
        else:
            _emit_sse(StageDEvent(
                event_type=StageDStatus.GROQ_TAXONOMY_SKIPPED,
                job_id=job_id,
                taxonomy={
                    "parent": groq_taxonomy.parent_category,
                    "child": groq_taxonomy.child_category,
                    "intent": groq_taxonomy.intent,
                },
                details={"notes": groq_taxonomy.fallback_notes},
            ))

        # Step 6 — Build V3 TaxonomyResult and ExtractedItems
        taxonomy_result = TaxonomyResult(
            parent_category=groq_taxonomy.parent_category,
            child_category=groq_taxonomy.child_category,
            intent=groq_taxonomy.intent,
            confidence=round(groq_taxonomy.confidence, 3),
            groq_taxonomy_used=groq_taxonomy.groq_used,
        )

        items: list[ExtractedItem] = []
        for entity in evidence_graph.entities:
            item_type = entity.entity_type
            if item_type == "unknown":
                if taxonomy_result.parent_category == "Shopping":
                    item_type = "product"
                else:
                    item_type = "topic"

            if item_type not in ["product", "person", "place", "topic"]:
                item_type = "topic"

            items.append(ExtractedItem(
                name=entity.name,
                item_type=item_type,
                timestamp=(
                    entity.mentioned_at[0]
                    if entity.mentioned_at else None
                ),
                confidence=round(entity.confidence, 3),
            ))

        # Step 7 — Build confidence dict
        overall = round(
            (taxonomy_result.confidence + evidence_graph.confidence) / 2.0,
            3,
        )
        confidence_dict = {
            "taxonomy": taxonomy_result.confidence,
            "evidence_graph": evidence_graph.confidence,
            "overall": overall,
        }

        # Step 8 — Build summary
        summary = evidence_graph.groq_summary or (
            f"Video about {evidence_graph.dominant_subject or 'unknown topic'}"
        )

        # Step 9 — Assemble V3 FinalResponse
        v3_output = FinalResponse(
            job_id=job_uuid,
            taxonomy=taxonomy_result,
            summary=summary,
            items=items,
            confidence=confidence_dict,
            fallback_notes=groq_taxonomy.fallback_notes,
        )

        # Step 10 — Persist to final_outputs table
        from ytclfr.db.models.final_output import FinalOutputModel

        content_type_str = (
            V3_CONTENT_TYPE_PREFIX
            + taxonomy_result.parent_category.lower().replace(" ", "_")
        )

        with db_session() as session:
            existing = session.query(FinalOutputModel).filter(
                FinalOutputModel.job_id == job_uuid
            ).first()

            output_json_dict = v3_output.model_dump(mode="json")
            overall_confidence = confidence_dict["overall"]

            if existing:
                existing.content_type = content_type_str
                existing.overall_confidence = overall_confidence
                existing.output_json = output_json_dict
                session.commit()
            else:
                new_record = FinalOutputModel(
                    job_id=job_uuid,
                    content_type=content_type_str,
                    overall_confidence=overall_confidence,
                    output_json=output_json_dict,
                )
                session.add(new_record)
                session.commit()
                session.refresh(new_record)

        # Step 11 — Set job status to completed
        with db_session() as session:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if job:
                job.status = "completed"
                session.commit()

        # Step 12 — Emit COMPLETE SSE
        _emit_sse(StageDEvent(
            event_type=StageDStatus.COMPLETE,
            job_id=job_id,
            taxonomy={
                "parent": taxonomy_result.parent_category,
                "child": taxonomy_result.child_category,
                "intent": taxonomy_result.intent,
            },
            details={
                "overall_confidence": confidence_dict["overall"],
                "item_count": len(items),
                "groq_taxonomy_used": groq_taxonomy.groq_used,
                "content_type": content_type_str,
            },
        ))

        logger.info(
            "V3 Stage D complete for job %s: %s / %s (conf=%.2f)",
            job_id,
            taxonomy_result.parent_category,
            taxonomy_result.child_category,
            taxonomy_result.confidence,
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "parent_category": taxonomy_result.parent_category,
            "child_category": taxonomy_result.child_category,
            "intent": taxonomy_result.intent,
            "confidence": confidence_dict["overall"],
        }

    except Exception as exc:
        logger.error(
            "V3 Stage D failed for job %s: %s",
            job_id, exc, exc_info=True,
        )
        try:
            with db_session() as err_session:
                job_err = err_session.query(Job).filter(
                    Job.id == job_uuid
                ).first()
                if job_err:
                    job_err.status = "v3_stage_d_failed"
                    job_err.error_message = str(exc)
                    err_session.commit()
        except Exception:
            pass

        _emit_sse(StageDEvent(
            event_type=StageDStatus.FAILED,
            job_id=job_id,
            error=str(exc),
        ))
        raise self.retry(exc=exc, countdown=30)
