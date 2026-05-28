import uuid
from typing import Any

from ytclfr.core.logging import get_logger
from ytclfr.db.session import db_session
from ytclfr.db.models.job import Job
from ytclfr.queue.celery_app import celery_app
from ytclfr.storage.manifest_store import SignalManifestStore
from ytclfr.tasks.v3.v3_extraction_tasks import v3_run_asr

logger = get_logger(__name__)

@celery_app.task(bind=True, name="ytclfr.tasks.v3.stage_b_extraction.v3_run_extraction_orchestrator", queue="fast", max_retries=3, default_retry_delay=30)
def v3_run_extraction_orchestrator(self: Any, job_id: str) -> dict[str, Any]:
    job_uuid = uuid.UUID(job_id)
    
    with db_session() as db:
        job = db.query(Job).filter(Job.id == job_uuid).first()
        if not job:
            raise ValueError("Job not found " + job_id)
            
        store = SignalManifestStore()
        manifest = store.get_by_job_id(db, job_uuid)
        if not manifest:
            raise ValueError("Manifest not found for job " + job_id)
            
        job.status = "v3_stage_b_running"
        db.commit()
        
        # Decide which extractors to run
        if manifest.has_speech:
            v3_run_asr.delay(job_id)
            
        # OCR will be paddle_ocr - stub for now, will call paddle OCR task if created
        if manifest.ocr_required:
            logger.info("OCR required but not implemented yet in V3 extractor tasks")
            
        from ytclfr.tasks.v3.stage_c_fusion import v3_run_evidence_fusion
        # For simplicity, chain fusion after ASR or immediately if no ASR
        # In a real celery setup we would use chords, but we can just delay it and it will wait for bundle?
        # Actually in V3, extraction tasks update the bundle, and then stage C is triggered.
        # We can just delay stage C and let it retry if bundle isn't ready, or chord it.
        # Let's just enqueue stage C for now.
        v3_run_evidence_fusion.apply_async((job_id,), countdown=10)
        
    return {"job_id": job_id, "status": "orchestrating"}
