import uuid
from typing import Any

from ytclfr.core.logging import get_logger
from ytclfr.db.session import db_session
from ytclfr.db.models.job import Job
from ytclfr.db.models.v3.v3_extractor_bundles import V3ExtractorBundleORM
from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM
from ytclfr.queue.celery_app import celery_app
from ytclfr.tasks.v3.stage_d_taxonomy import v3_run_taxonomy_mapping
from celery.exceptions import Retry
from ytclfr.storage.manifest_store import SignalManifestStore
from ytclfr.core.config import get_settings
from ytclfr.contracts.v3.evidence import FusedSegment, EvidenceGraph, ExtractedEntity
from ytclfr.contracts.v3.bundle import ASRCompletenessMetrics
from ytclfr.fusion.v3_conflict_resolver import v3_resolve_conflicts
from ytclfr.fusion.v3_groq_reasoner import v3_reason_over_evidence
from ytclfr.fusion.entity_extractor import extract_entities_from_timeline
from ytclfr.probing.ocr_pattern_scorer import score_ocr_patterns

logger = get_logger(__name__)

@celery_app.task(bind=True, name="ytclfr.tasks.v3.stage_c_fusion.v3_run_evidence_fusion", queue="fast", max_retries=3, default_retry_delay=30)
def v3_run_evidence_fusion(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    # Extract job_id whether called directly or via chord callback
    job_id = args[-1] if args else kwargs.get("job_id")
    if not job_id:
        raise ValueError("job_id not provided")
        
    job_uuid = uuid.UUID(job_id)
    
    with db_session() as db:
        try:
            job = db.query(Job).filter(Job.id == job_uuid).first()
            if not job:
                raise ValueError("Job not found " + job_id)
                
            bundle = db.query(V3ExtractorBundleORM).filter(V3ExtractorBundleORM.job_id == job_uuid).first()
            if not bundle:
                logger.warning("Bundle not ready for job " + job_id)
                raise self.retry(countdown=10)
                
            # Check idempotency
            existing = db.query(V3EvidenceGraphORM).filter(V3EvidenceGraphORM.job_id == job_uuid).first()
            if existing:
                v3_run_taxonomy_mapping.delay(job_id)
                return {"job_id": job_id, "status": "skipped"}
                
            job.status = "v3_stage_c_running"
            db.commit()

            # Parse segments
            asr_segs = []
            if isinstance(bundle.asr_segments_json, list):
                for s in bundle.asr_segments_json:
                    asr_segs.append(FusedSegment(
                        timestamp=float(s.get("start_time", 0.0)),
                        end_timestamp=float(s.get("end_time", 0.0)) if "end_time" in s else None,
                        text=str(s.get("text", "")),
                        source="asr",
                        confidence=float(s.get("confidence", 0.0))
                    ))
            
            ocr_segs = []
            if isinstance(bundle.ocr_segments_json, list):
                for s in bundle.ocr_segments_json:
                    ocr_segs.append(FusedSegment(
                        timestamp=float(s.get("start_time", s.get("frame_timestamp", 0.0))),
                        end_timestamp=float(s.get("end_time", 0.0)) if "end_time" in s else None,
                        text=str(s.get("text", "")),
                        source="ocr",
                        confidence=float(s.get("confidence", 0.0))
                    ))

            asr_metrics = None
            if isinstance(bundle.asr_metrics_json, dict) and bundle.asr_metrics_json:
                asr_metrics = ASRCompletenessMetrics(**bundle.asr_metrics_json)

            manifest = SignalManifestStore().get_by_job_id(db, job_uuid)
            if not manifest:
                raise ValueError("Manifest not found")

            conflict_res = v3_resolve_conflicts(
                asr_segments=asr_segs,
                ocr_segments=ocr_segs,
                structural_video_type=manifest.structural_video_type,
                manifest=manifest,
                asr_metrics=asr_metrics,
            )

            final_asr = conflict_res.adjusted_asr_segments if conflict_res.adjusted_asr_segments is not None else asr_segs
            final_ocr = conflict_res.adjusted_ocr_segments if conflict_res.adjusted_ocr_segments is not None else ocr_segs
            all_segments = final_asr + final_ocr
            all_segments.sort(key=lambda x: x.timestamp)

            # score_ocr_patterns analyzes the FULL OCR transcript across
            # the whole video (unlike Stage A's sparse frame sample), so
            # it can catch a countdown/ranked-list structure that Stage
            # A's initial gate missed. This module already existed,
            # fully tested, but was never called from anywhere.
            ocr_pattern_result = score_ocr_patterns(final_ocr)
            effective_structural_type = manifest.structural_video_type
            if (
                effective_structural_type in ("none", "unknown")
                and ocr_pattern_result.countdown_likelihood >= 0.5
            ):
                effective_structural_type = "countdown"
            elif (
                effective_structural_type in ("none", "unknown")
                and ocr_pattern_result.ordinal_pattern_score >= 0.5
            ):
                effective_structural_type = "list"

            # Heuristic entity extraction gives us a deterministic baseline
            # (ranked-list items, Title-Case phrases) before Groq ever runs,
            # so a video still gets real entities even if Groq is unavailable,
            # and Groq gets real candidates to refine instead of a cold blob
            # of raw transcript text. entity_extractor only reads seg.text /
            # seg.timestamp, so it works fine against FusedSegment even though
            # it was originally written against the legacy AlignedSegment type.
            heuristic_entities = [
                ExtractedEntity(
                    name=e.name,
                    entity_type=e.entity_type,
                    mentioned_at=e.mentioned_at,
                    confidence=e.confidence,
                )
                for e in extract_entities_from_timeline(all_segments)  # type: ignore[arg-type]
            ]

            evidence_graph = EvidenceGraph(
                job_id=job_uuid,
                structural_video_type=effective_structural_type,
                primary_evidence_modality=conflict_res.primary_evidence_modality,
                segments=all_segments,
                entities=heuristic_entities,
                confidence=1.0,
                total_segments=len(all_segments)
            )

            settings = get_settings()
            groq_res = v3_reason_over_evidence(evidence_graph, settings)

            # Prefer Groq's refined entities when reasoning actually
            # succeeded and returned something; otherwise keep the
            # heuristic baseline rather than persisting an empty list.
            if groq_res.reasoning_used and groq_res.refined_entities:
                final_entities_json = groq_res.refined_entities
            else:
                final_entities_json = [e.model_dump(mode="json") for e in heuristic_entities]

            new_graph = V3EvidenceGraphORM(
                job_id=job_uuid,
                segments_json={"segments": [s.model_dump() for s in all_segments]},
                entities_json={"entities": final_entities_json},
                dominant_subject=groq_res.dominant_subject or "Unknown topic",
                groq_summary=groq_res.summary or "Summarized content",
                scene_boundaries_json={"boundaries": groq_res.scene_boundaries},
                groq_reasoning_used=groq_res.reasoning_used,
                modality_coverage_json={"asr": 1.0 if final_asr else 0.0, "ocr": 1.0 if final_ocr else 0.0},
                conflict_count=conflict_res.conflict_count,
                conflict_details_json={"details": conflict_res.conflict_details},
                structural_video_type=effective_structural_type,
                evidence_priority_notes_json={"notes": conflict_res.evidence_priority_notes},
                primary_evidence_modality=conflict_res.primary_evidence_modality,
                total_segments=len(all_segments),
                confidence=0.9
            )
            db.add(new_graph)
            
            job.status = "v3_stage_c_complete"
            db.commit()
            
            v3_run_taxonomy_mapping.delay(job_id)
            
            return {"job_id": job_id, "status": "fused"}

        except Retry:
            raise
        except Exception as exc:
            db.rollback()
            if self.request.retries >= self.max_retries:
                try:
                    job_obj = db.query(Job).filter(Job.id == job_uuid).first()
                    if job_obj:
                        job_obj.status = "dead_letter"
                        job_obj.error_message = str(exc)
                        db.commit()
                except Exception:
                    pass
                logger.error(
                    "Stage C fusion exhausted all retries for job %s: %s",
                    job_id,
                    str(exc),
                )
                return {
                    "job_id": str(job_id),
                    "status": "failed",
                }
            raise self.retry(exc=exc)
