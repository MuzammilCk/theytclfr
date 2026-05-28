"""Celery task for V3 Stage C — Evidence Fusion.

v3_run_evidence_fusion is the chord callback for V3 jobs.
It replaces run_fuse_evidence for V3 pipeline jobs and uses:
- V3 contracts (contracts.v3.evidence)
- V3 conflict resolver (fusion.v3_conflict_resolver) with ASR degradation detection
- V3 Groq reasoner (fusion.v3_groq_reasoner) with structured JSON prompts
- V3 DB tables (v3_evidence_graphs)
"""

import json
from collections import defaultdict
from uuid import UUID

from sqlalchemy.sql import func

from ytclfr.contracts.events import StageCEvent, StageCStatus
from ytclfr.contracts.v3.evidence import (
    EvidenceGraph,
    ExtractedEntity,
    FusedSegment,
)
from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM
from ytclfr.db.models.v3.v3_extractor_bundles import V3ExtractorBundleORM
from ytclfr.db.session import db_session
from ytclfr.queue.celery_app import celery_app

logger = get_logger(__name__)

# ── MODULE-LEVEL CONSTANTS ──────────────────────────────────

MIN_CONFIDENCE_THRESHOLD: float = 0.0

_settings = get_settings()


from ytclfr.core.serialization import _sanitize_for_json


def _emit_sse(event: StageCEvent) -> None:
    """Publish a StageCEvent to Redis SSE channel."""
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


@celery_app.task(
    bind=True,
    name="ytclfr.tasks.v3.stage_c_fusion.v3_run_evidence_fusion",
    queue="fast",
    max_retries=2,
    default_retry_delay=30,
)
def v3_run_evidence_fusion(
    self,
    extractor_results: list[dict],
    job_id: str,
) -> dict[str, object]:
    """V3 chord callback: fuse extracted evidence into EvidenceGraph.

    Uses V3 contracts, V3 conflict resolver (with ASR degradation),
    and V3 Groq reasoner (with structured JSON prompts).
    Persists to v3_evidence_graphs table.
    """
    job_uuid = UUID(job_id)

    # Step 1 — Log chord results and emit STARTED SSE
    for er in extractor_results:
        logger.info(
            "V3 Stage C chord result for job %s: type=%s status=%s",
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
        # Step 2 — Set job status, load manifest
        settings = get_settings()
        with db_session() as session:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            job.status = "v3_stage_c_running"

            from ytclfr.storage.manifest_store import SignalManifestStore
            manifest_store = SignalManifestStore()
            manifest = manifest_store.get_by_job_id(session, job_uuid)

            session.commit()

        # Step 3 — Fetch full extractor results from DB
        from ytclfr.tasks.align import _fetch_extractor_results_from_db
        db_extractor_results = _fetch_extractor_results_from_db(job_uuid)

        # Step 3.5 — Post-OCR structural analysis
        ocr_results = next(
            (r for r in db_extractor_results if r.get("extractor_type") == "ocr"),
            None,
        )
        if ocr_results and ocr_results.get("segments"):
            from ytclfr.probing.ocr_pattern_scorer import score_ocr_patterns
            pattern_scores = score_ocr_patterns(ocr_results["segments"])

            with db_session() as session:
                manifest_store.update_structural_scores(
                    session=session,
                    job_id=job_uuid,
                    ordinal_score=pattern_scores.ordinal_pattern_score,
                    countdown_score=pattern_scores.countdown_likelihood,
                )

            if manifest:
                manifest.ordinal_pattern_score = pattern_scores.ordinal_pattern_score
                manifest.countdown_likelihood = pattern_scores.countdown_likelihood

        # Step 3.6 — Persist ExtractorBundle to V3 table
        asr_segs = []
        ocr_segs = []
        audio_segs = []
        asr_metrics_json = None
        total_duration = 0.0

        for r in db_extractor_results:
            etype = r.get("extractor_type")
            segments = r.get("segments", [])
            if etype == "asr":
                asr_segs = segments
                total_duration = r.get("total_duration_seconds", 0.0)
            elif etype == "ocr":
                ocr_segs = segments
            elif etype == "audio":
                audio_segs = segments

        with db_session() as session:
            existing_bundle = session.query(V3ExtractorBundleORM).filter(
                V3ExtractorBundleORM.job_id == job_uuid
            ).first()
            if existing_bundle:
                existing_bundle.asr_segments_json = asr_segs
                existing_bundle.ocr_segments_json = ocr_segs
                existing_bundle.audio_segments_json = audio_segs
                existing_bundle.asr_metrics_json = asr_metrics_json
                existing_bundle.total_duration_seconds = total_duration
                session.commit()
            else:
                bundle_orm = V3ExtractorBundleORM(
                    job_id=job_uuid,
                    asr_segments_json=asr_segs,
                    ocr_segments_json=ocr_segs,
                    audio_segments_json=audio_segs,
                    asr_metrics_json=asr_metrics_json,
                    total_duration_seconds=total_duration,
                )
                session.add(bundle_orm)
                session.commit()

        # Step 4 — Run V1 alignment engine (reused, version-agnostic)
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
            "V3 Stage C alignment done for job %s: %d segments, confidence=%.2f",
            job_id,
            timeline.total_segments,
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

        # Step 6 — Build FusedSegment list (V3 contracts)
        structural_video_type = manifest.structural_video_type if manifest else "none"

        fused_segments: list[FusedSegment] = []
        entity_names_at: dict[float, set[str]] = defaultdict(set)
        for entity in heuristic_entities:
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

        # Step 7 — V3 Conflict Resolution (with ASR degradation detection)
        from ytclfr.fusion.v3_conflict_resolver import v3_resolve_conflicts
        from ytclfr.contracts.v3.bundle import ASRCompletenessMetrics

        asr_fused = [s for s in fused_segments if s.source == "asr"]
        ocr_fused = [s for s in fused_segments if s.source == "ocr"]

        # Load ASR metrics if available (from V3 ASR extractor)
        asr_metrics = None
        if asr_metrics_json:
            try:
                asr_metrics = ASRCompletenessMetrics.model_validate(asr_metrics_json)
            except Exception:
                pass

        conflict_resolution = v3_resolve_conflicts(
            asr_segments=asr_fused,
            ocr_segments=ocr_fused,
            structural_video_type=structural_video_type,
            manifest=manifest,
            asr_metrics=asr_metrics,
        )

        # Apply adjusted segments
        if conflict_resolution.adjusted_asr_segments is not None:
            non_asr = [s for s in fused_segments if s.source != "asr"]
            fused_segments = non_asr + conflict_resolution.adjusted_asr_segments
            fused_segments.sort(key=lambda s: s.timestamp)

        if conflict_resolution.adjusted_ocr_segments is not None:
            non_ocr = [s for s in fused_segments if s.source != "ocr"]
            fused_segments = non_ocr + conflict_resolution.adjusted_ocr_segments
            fused_segments.sort(key=lambda s: s.timestamp)

        modality_coverage = {
            "asr": len(asr_fused) / max(1, len(fused_segments)),
            "ocr": len(ocr_fused) / max(1, len(fused_segments)),
            "visual": 1.0,
        }

        # Step 8 — Build V3 EvidenceGraph (unfrozen for construction, then freeze)
        # Convert heuristic entities to V3 ExtractedEntity format
        v3_entities: list[ExtractedEntity] = []
        for e in heuristic_entities:
            v3_entities.append(ExtractedEntity(
                name=e.name,
                entity_type=e.entity_type,
                mentioned_at=list(e.mentioned_at),
                confidence=e.confidence,
            ))

        graph = EvidenceGraph(
            job_id=job_uuid,
            segments=fused_segments,
            entities=v3_entities,
            dominant_subject=None,  # Will be set by Groq in Stage D
            groq_summary=None,
            scene_boundaries=[],
            groq_reasoning_used=False,
            modality_coverage=modality_coverage,
            conflict_count=conflict_resolution.conflict_count,
            conflict_details=conflict_resolution.conflict_details,
            structural_video_type=structural_video_type,
            evidence_priority_notes=conflict_resolution.evidence_priority_notes,
            primary_evidence_modality=conflict_resolution.primary_evidence_modality,
            total_segments=len(fused_segments),
            confidence=round(verdict.aggregate_score.overall, 3),
        )

        # Step 8.5 — V3 Groq Reasoning (structured JSON prompt)
        from ytclfr.fusion.v3_groq_reasoner import v3_reason_over_evidence

        groq_result = v3_reason_over_evidence(
            evidence_graph=graph,
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

            # Update entities with Groq-refined data if available
            if groq_result.refined_entities:
                v3_entities = []
                for e in groq_result.refined_entities:
                    valid_types = {"product", "person", "place", "topic", "unknown"}
                    etype = e.get("type", "unknown")
                    if etype not in valid_types:
                        etype = "unknown"
                    v3_entities.append(ExtractedEntity(
                        name=e["name"],
                        entity_type=etype,
                        mentioned_at=e.get("timestamps", [])[:10],
                        confidence=0.85,
                    ))

            # Rebuild graph with Groq results
            graph = EvidenceGraph(
                job_id=job_uuid,
                segments=fused_segments,
                entities=v3_entities,
                dominant_subject=groq_result.dominant_subject,
                groq_summary=groq_result.summary,
                scene_boundaries=groq_result.scene_boundaries,
                groq_reasoning_used=True,
                modality_coverage=modality_coverage,
                conflict_count=conflict_resolution.conflict_count,
                conflict_details=conflict_resolution.conflict_details,
                structural_video_type=structural_video_type,
                evidence_priority_notes=conflict_resolution.evidence_priority_notes,
                primary_evidence_modality=conflict_resolution.primary_evidence_modality,
                total_segments=len(fused_segments),
                confidence=round(verdict.aggregate_score.overall, 3),
            )
        else:
            _emit_sse(StageCEvent(
                event_type=StageCStatus.GROQ_SKIPPED,
                job_id=job_id,
            ))

        # Step 9 — Persist to V3 evidence_graphs table
        with db_session() as session:
            existing = session.query(V3EvidenceGraphORM).filter(
                V3EvidenceGraphORM.job_id == job_uuid
            ).first()

            segments_data = {"segments": [s.model_dump(mode="json") for s in graph.segments]}
            entities_data = {"entities": [e.model_dump(mode="json") for e in graph.entities]}
            boundaries_data = {"boundaries": graph.scene_boundaries}
            coverage_data = graph.modality_coverage
            conflicts_data = {"details": graph.conflict_details}
            priority_data = {"notes": graph.evidence_priority_notes}

            if existing:
                existing.segments_json = segments_data
                existing.entities_json = entities_data
                existing.dominant_subject = graph.dominant_subject
                existing.groq_summary = graph.groq_summary
                existing.scene_boundaries_json = boundaries_data
                existing.groq_reasoning_used = graph.groq_reasoning_used
                existing.modality_coverage_json = coverage_data
                existing.conflict_count = graph.conflict_count
                existing.conflict_details_json = conflicts_data
                existing.structural_video_type = graph.structural_video_type
                existing.evidence_priority_notes_json = priority_data
                existing.primary_evidence_modality = graph.primary_evidence_modality
                existing.total_segments = graph.total_segments
                existing.confidence = graph.confidence
                session.commit()
                orm_graph_id = str(existing.id)
            else:
                orm_graph = V3EvidenceGraphORM(
                    job_id=job_uuid,
                    segments_json=segments_data,
                    entities_json=entities_data,
                    dominant_subject=graph.dominant_subject,
                    groq_summary=graph.groq_summary,
                    scene_boundaries_json=boundaries_data,
                    groq_reasoning_used=graph.groq_reasoning_used,
                    modality_coverage_json=coverage_data,
                    conflict_count=graph.conflict_count,
                    conflict_details_json=conflicts_data,
                    structural_video_type=graph.structural_video_type,
                    evidence_priority_notes_json=priority_data,
                    primary_evidence_modality=graph.primary_evidence_modality,
                    total_segments=graph.total_segments,
                    confidence=graph.confidence,
                )
                session.add(orm_graph)
                session.commit()
                session.refresh(orm_graph)
                orm_graph_id = str(orm_graph.id)

        # Step 10 — Update job status
        with db_session() as session:
            job = session.query(Job).filter(Job.id == job_uuid).first()
            if job:
                job.status = "v3_stage_c_complete"
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
            evidence_graph_id=orm_graph_id,
            details={
                "total_segments": graph.total_segments,
                "entity_count": len(graph.entities),
                "groq_used": graph.groq_reasoning_used,
                "dominant_subject": graph.dominant_subject,
            },
        ))

        # Step 13 — Trigger Stage D
        from ytclfr.tasks.v3.stage_d_taxonomy import v3_run_taxonomy_mapping
        v3_run_taxonomy_mapping.delay(job_id)
        logger.info("V3 Stage D triggered for job %s", job_id)

        return {
            "job_id": job_id,
            "status": "v3_evidence_fused",
            "total_segments": graph.total_segments,
            "entity_count": len(graph.entities),
            "groq_reasoning_used": graph.groq_reasoning_used,
        }

    except Exception as exc:
        logger.error(
            "V3 Stage C failed for job %s: %s",
            job_id, exc, exc_info=True,
        )
        # Attempt S3 cleanup on failure too
        try:
            from ytclfr.ingestion.s3_storage import S3StorageManager
            s3_manager = S3StorageManager(get_settings())
            s3_manager.delete_directory(prefix=f"{job_id}/")
        except Exception as cleanup_exc:
            logger.warning("Failed to cleanup S3 for failed job %s: %s", job_id, cleanup_exc)

        try:
            with db_session() as err_session:
                job_err = err_session.query(Job).filter(
                    Job.id == job_uuid
                ).first()
                if job_err:
                    job_err.status = "v3_stage_c_failed"
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
