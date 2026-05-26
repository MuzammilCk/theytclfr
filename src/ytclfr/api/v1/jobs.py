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

    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    youtube_url: str
    video_title: str | None
    channel_name: str | None
    duration_seconds: float | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

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

    download_video.delay(str(job.id))

    return JobResponse(
        job_id=job.id,
        status=job.status,
        youtube_url=job.youtube_url,
        created_at=job.created_at,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
@limiter.limit("30/minute")
def get_job_status(
    request: Request,
    job_id: UUID,
    db: Session = Depends(get_db),
    _token: typing.Any = Depends(require_auth),
) -> JobStatusResponse:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        youtube_url=job.youtube_url,
        video_title=job.video_title,
        channel_name=job.channel_name,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
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

    # Determine checkpoint
    from ytclfr.storage.manifest_store import SignalManifestStore
    from ytclfr.storage.evidence_store import EvidenceGraphStore
    
    if job.s3_video_uri is None:
        resumed_from = "download_video"
        download_video.delay(str(job_id))
    else:
        manifest_store = SignalManifestStore()
        manifest = manifest_store.get_by_job_id(db, job_id)
        if not manifest:
            resumed_from = "run_signal_census"
            from ytclfr.tasks.stage_a import run_signal_census
            run_signal_census.delay(str(job_id))
        else:
            evidence_store = EvidenceGraphStore()
            evidence = evidence_store.get_by_job_id(db, job_id)
            if evidence:
                resumed_from = "run_taxonomy_mapping"
                from ytclfr.tasks.stage_d import run_taxonomy_mapping
                run_taxonomy_mapping.delay(str(job_id))
            else:
                resumed_from = "run_targeted_extraction"
                from ytclfr.tasks.stage_b import run_targeted_extraction
                run_targeted_extraction.delay(str(job_id))

    job.status = "pending"
    job.error_message = None
    db.commit()

    return RetryResponse(
        job_id=job_id,
        message="Job recovery initiated",
        resumed_from=resumed_from
    )
