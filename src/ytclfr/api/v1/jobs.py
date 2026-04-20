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
