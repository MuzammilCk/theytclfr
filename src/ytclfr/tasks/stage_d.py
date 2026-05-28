"""Celery task for Stage D — Taxonomy + Intent Mapping.

run_taxonomy_mapping is the terminal V2 pipeline task.
It reads the EvidenceGraph from Stage C, classifies the
taxonomy (Groq + rule-based fallback), and persists a
V2FinalOutput to the existing final_outputs table.

After this task, job.status = "completed".
"""

# ── TOP-LEVEL IMPORTS ────────────────────────────────────────
import json
from uuid import UUID

from ytclfr.contracts.events import StageDEvent, StageDStatus
from ytclfr.contracts.v2_output import (
    ExtractedItem,
    TaxonomyResult,
    V2FinalOutput,
)
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.queue.celery_app import celery_app
from ytclfr.storage.evidence_store import EvidenceGraphStore

logger = get_logger(__name__)

# ── MODULE-LEVEL CONSTANTS ──────────────────────────────────

# Content type prefix for V2 outputs in final_outputs table.
# Allows V1 API to distinguish V2 records.
# # PIPELINE-WIRING-TODO: Update GET /results endpoint (W-6) to
# # serve V2FinalOutput when content_type starts with "v2_".
V2_CONTENT_TYPE_PREFIX: str = "v2_"

# Maximum fused segments to include in evidence_graph_summary
# (kept small to avoid large JSON payloads in output_json).
MAX_EVIDENCE_SUMMARY_SEGMENTS: int = 20

# ── MODULE-LEVEL SINGLETONS ─────────────────────────────────

_evidence_store = EvidenceGraphStore()

# ── SSE HELPER ──────────────────────────────────────────────

def _emit_sse(event: StageDEvent) -> None:
    """Publish a StageDEvent to Redis SSE channel.
    Failure logs WARNING but never raises."""
    import redis

    settings = get_settings()
    channel = f"job:{event.job_id}:events"
    try:
        r = redis.Redis.from_url(settings.redis_url)
        payload = event.model_dump(mode="json")
        r.publish(channel, json.dumps(payload))
        logger.info("SSE emitted to %s: %s", channel, event.event_type)
    except Exception as exc:
        logger.warning(
            "Failed to emit SSE event %s: %s",
            event.event_type, exc
        )


# ── TASK DEFINITION ─────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="ytclfr.tasks.stage_d.run_taxonomy_mapping",
    queue="fast",
    max_retries=2,
    default_retry_delay=30,
)
def run_taxonomy_mapping(
    self,
    job_id: str,
) -> dict[str, object]:
    """Read EvidenceGraph and produce V2 FinalOutput with taxonomy.

    Terminal task of the V2 pipeline. Sets job.status = "completed".

    Args:
        job_id: String UUID of the job to classify.

    Returns:
        Dict with job_id, status, parent_category, child_category.
    """
    job_uuid = UUID(job_id)

    try:
        # Step 1 — Emit STARTED:
        _emit_sse(StageDEvent(
            event_type=StageDStatus.STARTED,
            job_id=job_id,
        ))

        # Step 2 — Set job status to stage_d_running:
        settings = get_settings()
        with db_session() as session:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            job.status = "stage_d_running"
            session.commit()
            signal_manifest_has_speech = True   # safe default
            signal_manifest_has_music = False   # safe default
            # Try to load SignalManifest for signal context
            from ytclfr.storage.manifest_store import SignalManifestStore
            manifest_store = SignalManifestStore()
            manifest = manifest_store.get_by_job_id(session, job_uuid)
            if manifest:
                signal_manifest_has_speech = manifest.has_speech
                signal_manifest_has_music = manifest.has_music

            # Step 3 — Idempotency check:
            # (Perform AFTER setting stage_d_running, INSIDE the DB session)
            # Check if a V2 final_output record already exists:
            from ytclfr.db.models.final_output import FinalOutputModel
            existing = session.query(FinalOutputModel).filter(
                FinalOutputModel.job_id == job_uuid,
            ).first()
            if existing and existing.content_type.startswith(
                V2_CONTENT_TYPE_PREFIX
            ):
                logger.warning(
                    "Stage D idempotency hit for job %s — "
                    "V2 FinalOutput already exists, skipping",
                    job_id,
                )
                return {
                    "job_id": job_id,
                    "status": "skipped",
                    "reason": "V2 FinalOutput already persisted",
                }

        # Step 4 — Load EvidenceGraph from DB:
        with db_session() as session:
            evidence_graph = _evidence_store.get_by_job_id(
                session, job_uuid
            )
        if not evidence_graph:
            raise ValueError(
                f"EvidenceGraph not found for job {job_id}. "
                "Stage C must complete before Stage D."
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

        # Step 5 — Taxonomy classification:
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

        # Step 6 — Build TaxonomyResult and ExtractedItems:
        taxonomy_result = TaxonomyResult(
            parent_category=groq_taxonomy.parent_category,
            child_category=groq_taxonomy.child_category,
            intent=groq_taxonomy.intent,
            confidence=round(groq_taxonomy.confidence, 3),
            groq_taxonomy_used=groq_taxonomy.groq_used,
        )

        # Map EvidenceGraph entities → ExtractedItem
        # Only map entities with known types (not "unknown")
        items: list[ExtractedItem] = []
        for entity in evidence_graph.entities:
            item_type = entity.entity_type
            if item_type == "unknown":
                # Guess from taxonomy context
                if taxonomy_result.parent_category == "Shopping":
                    item_type = "product"
                else:
                    item_type = "topic"

            if item_type not in ["product", "person", "place", "topic"]:
                item_type = "topic" # Fallback to a valid literal if somehow invalid

            items.append(ExtractedItem(
                name=entity.name,
                item_type=item_type,
                timestamp=(
                    entity.mentioned_at[0]
                    if entity.mentioned_at else None
                ),
                confidence=round(entity.confidence, 3),
            ))

        # Step 7 — Build evidence_graph_summary (sample segments):
        evidence_summary = [
            {
                "timestamp": seg.timestamp,
                "end_timestamp": seg.end_timestamp,
                "text": seg.text,
                "source": seg.source,
                "confidence": seg.confidence,
            }
            for seg in evidence_graph.segments[:MAX_EVIDENCE_SUMMARY_SEGMENTS]
        ]

        # Step 8 — Build provenance dict:
        provenance = {
            "taxonomy_evidence": {
                "dominant_subject": evidence_graph.dominant_subject,
                "scene_boundaries": evidence_graph.scene_boundaries[:5],
                "entity_count": len(evidence_graph.entities),
                "groq_summary_used": evidence_graph.groq_reasoning_used,
            },
            "taxonomy_method": (
                "groq" if groq_taxonomy.groq_used else "rule_based"
            ),
        }

        # Step 9 — Build confidence dict:
        overall = round(
            (taxonomy_result.confidence + evidence_graph.confidence) / 2.0,
            3
        )
        confidence_dict = {
            "taxonomy": taxonomy_result.confidence,
            "evidence_graph": evidence_graph.confidence,
            "overall": overall,
        }

        # Step 10 — Assemble V2FinalOutput:
        v2_output = V2FinalOutput(
            job_id=job_uuid,
            taxonomy=taxonomy_result,
            summary=evidence_graph.groq_summary or (
                f"Video about {evidence_graph.dominant_subject or 'unknown topic'}"
            ),
            items=items,
            evidence_graph_summary=evidence_summary,
            provenance=provenance,
            confidence=confidence_dict,
            fallback_notes=groq_taxonomy.fallback_notes,
        )

        # Step 11 — Persist to final_outputs table:
        from ytclfr.db.models.final_output import FinalOutputModel

        content_type_str = (
            V2_CONTENT_TYPE_PREFIX
            + taxonomy_result.parent_category.lower().replace(" ", "_")
        )

        with db_session() as session:
            existing = session.query(FinalOutputModel).filter(
                FinalOutputModel.job_id == job_uuid
            ).first()

            output_json_dict = v2_output.model_dump(mode="json")
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

        # Step 12 — Update job status to completed:
        with db_session() as session:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if job:
                job.status = "completed"
                session.commit()

        # Step 13 — Emit COMPLETE SSE:
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

        # Step 14 — PIPELINE-WIRING-TODO and return:
        # PIPELINE-WIRING-TODO: W-6 — Update GET /api/v1/jobs/{id}/results
        # to detect content_type.startswith("v2_") and deserialize
        # V2FinalOutput instead of V1 FinalOutput.

        logger.info(
            "Stage D complete for job %s: %s / %s (conf=%.2f)",
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
            "Stage D failed for job %s: %s",
            job_id, exc, exc_info=True,
        )
        try:
            with db_session() as err_session:
                job_err = err_session.query(Job).filter(
                    Job.id == job_uuid
                ).first()
                if job_err:
                    job_err.status = "stage_d_failed"
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
