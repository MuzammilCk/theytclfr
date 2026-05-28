import uuid
from typing import Any

from ytclfr.core.logging import get_logger
from ytclfr.db.session import db_session
from ytclfr.db.models.job import Job
from ytclfr.db.models.v3.v3_extractor_bundles import V3ExtractorBundleORM
from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM
from ytclfr.queue.celery_app import celery_app
from ytclfr.tasks.v3.stage_d_taxonomy import v3_run_taxonomy_mapping

logger = get_logger(__name__)

@celery_app.task(bind=True, name="ytclfr.tasks.v3.stage_c_fusion.v3_run_evidence_fusion", queue="fast", max_retries=3, default_retry_delay=30)
def v3_run_evidence_fusion(self: Any, job_id: str) -> dict[str, Any]:
    job_uuid = uuid.UUID(job_id)
    
    with db_session() as db:
        job = db.query(Job).filter(Job.id == job_uuid).first()
        if not job:
            raise ValueError("Job not found " + job_id)
            
        bundle = db.query(V3ExtractorBundleORM).filter(V3ExtractorBundleORM.job_id == job_uuid).first()
        if not bundle:
            logger.warning("Bundle not ready for job " + job_id)
            raise self.retry(countdown=10)
            
        # Perform Fusion (simplified for now to meet schema)
        # We should parse bundle.asr_segments_json, perform sliding window NLP, 
        # and extract entities.
        
        # Check idempotency
        existing = db.query(V3EvidenceGraphORM).filter(V3EvidenceGraphORM.job_id == job_uuid).first()
        if existing:
            v3_run_taxonomy_mapping.delay(job_id)
            return {"job_id": job_id, "status": "skipped"}
            
        job.status = "v3_stage_c_running"
        db.commit()

        # Build mock entities based on ASR or metadata for now, since we aren't calling Groq
        entities = []
        if isinstance(bundle.asr_segments_json, list) and len(bundle.asr_segments_json) > 0:
            for i, seg in enumerate(bundle.asr_segments_json[:5]): # just sample
                entities.append({
                    "entity_id": str(uuid.uuid4()),
                    "name": seg.get("text", "Unknown"),
                    "entity_type": "topic",
                    "confidence": 0.8,
                    "mentioned_at": [seg.get("start_time", 0.0)]
                })

        new_graph = V3EvidenceGraphORM(
            job_id=job_uuid,
            segments_json={"segments": []},
            entities_json={"entities": entities},
            dominant_subject="Unknown topic" if not entities else entities[0]["name"],
            groq_summary="Summarized content",
            scene_boundaries_json={"boundaries": []},
            groq_reasoning_used=False,
            modality_coverage_json={"asr": 1.0},
            conflict_count=0,
            conflict_details_json={"details": []},
            structural_video_type="none",
            evidence_priority_notes_json={"notes": []},
            primary_evidence_modality="mixed",
            total_segments=0,
            confidence=0.9
        )
        db.add(new_graph)
        
        job.status = "v3_stage_c_complete"
        db.commit()
        
        v3_run_taxonomy_mapping.delay(job_id)
        
    return {"job_id": job_id, "status": "fused"}
