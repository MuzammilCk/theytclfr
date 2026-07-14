import typing
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ytclfr.api.auth import require_auth
from ytclfr.api.rate_limit import limiter
from ytclfr.db.models.job import Job
from ytclfr.db.session import get_db
from ytclfr.ingestion.validator import validate_youtube_url
from ytclfr.tasks.ingest import download_video

router = APIRouter()

class SubmitJobRequest(BaseModel):
    youtube_url: str

class JobResponse(BaseModel):
    job_id: UUID
    status: str
    youtube_url: str
    created_at: datetime
    schema_version: str = "v3"
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)

@router.post("/jobs", response_model=JobResponse, status_code=201)
@limiter.limit("10/minute")
def submit_job(
    request: Request,
    req: SubmitJobRequest,
    db: Session = Depends(get_db),
    _token: typing.Any = Depends(require_auth),
) -> JobResponse:
    try:
        normalized_url = validate_youtube_url(req.youtube_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    job = Job(youtube_url=normalized_url, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    # Note: download_video will be updated to accept pipeline_version
    download_video.delay(str(job.id), pipeline_version="v3")
    
    import random
    if random.random() < 0.10:
        from ytclfr.tasks.v4_shadow.shadow_orchestrator import run_v4_shadow_pipeline
        run_v4_shadow_pipeline.apply_async(args=[str(job.id)], queue="heavy")

    return JobResponse(
        job_id=job.id,
        status=job.status,
        youtube_url=job.youtube_url,
        created_at=job.created_at,
        error_message=job.error_message,
    )

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _token: typing.Any = Depends(require_auth),
) -> JobResponse:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        job_id=job.id,
        status=job.status,
        youtube_url=job.youtube_url,
        created_at=job.created_at,
        error_message=job.error_message,
    )

class RetryResponse(BaseModel):
    job_id: UUID
    message: str
    resumed_from: str

@router.post("/jobs/{job_id}/retry", response_model=RetryResponse)
@limiter.limit("5/minute")
def retry_job(
    request: Request,
    job_id: UUID,
    db: Session = Depends(get_db),
    _token: typing.Any = Depends(require_auth),
) -> RetryResponse:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ("dead_letter", "failed"):
        raise HTTPException(status_code=400, detail="Job must be in dead_letter or failed state to retry")

    if job.s3_video_uri is None:
        resumed_from = "download_video"
        download_video.delay(str(job_id), pipeline_version="v3")
    else:
        from ytclfr.storage.manifest_store import SignalManifestStore
        from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM
        
        manifest = SignalManifestStore().get_by_job_id(db, job_id)
        if not manifest:
            resumed_from = "stage_a_census"
            from ytclfr.tasks.v3.stage_a_census import v3_run_signal_census
            v3_run_signal_census.delay(str(job_id))
        else:
            evidence = db.query(V3EvidenceGraphORM).filter(V3EvidenceGraphORM.job_id == job_id).first()
            if evidence:
                resumed_from = "stage_d_taxonomy"
                from ytclfr.tasks.v3.stage_d_taxonomy import v3_run_taxonomy_mapping
                v3_run_taxonomy_mapping.delay(str(job_id))
            else:
                resumed_from = "stage_b_extraction"
                from ytclfr.tasks.v3.stage_b_extraction import v3_run_targeted_extraction
                v3_run_targeted_extraction.delay(str(job_id))

    job.status = "pending"
    job.error_message = None
    db.commit()

    return RetryResponse(
        job_id=job_id,
        message="V3 Job recovery initiated",
        resumed_from=resumed_from
    )
