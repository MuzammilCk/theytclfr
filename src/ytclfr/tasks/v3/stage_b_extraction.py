import uuid
from typing import Any

from ytclfr.core.logging import get_logger
from ytclfr.db.session import db_session
from ytclfr.db.models.job import Job
from ytclfr.queue.celery_app import celery_app
from ytclfr.storage.manifest_store import SignalManifestStore
from ytclfr.tasks.v3.v3_extraction_tasks import v3_run_asr, v3_run_ocr
from celery import chord

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
        tasks = []
        if manifest.has_speech:
            tasks.append(v3_run_asr.s(job_id))
            
        if manifest.ocr_required:
            tasks.append(v3_run_ocr.s(job_id))
            
        from ytclfr.tasks.v3.stage_c_fusion import v3_run_evidence_fusion
        
        if tasks:
            chord(tasks)(v3_run_evidence_fusion.s(job_id))
        else:
            v3_run_evidence_fusion.delay(job_id)
        
    return {"job_id": job_id, "status": "orchestrating"}
