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
    from ytclfr.db.models.router_decision import RouterDecisionModel
    from ytclfr.db.models.extractor_result import ExtractorResultModel
    
    if job.s3_video_uri is None:
        resumed_from = "download_video"
        download_video.delay(str(job_id))
    else:
        decision = db.query(RouterDecisionModel).filter_by(job_id=job_id).first()
        if not decision:
            resumed_from = "classify_video"
            from ytclfr.tasks.route import classify_video
            classify_video.delay(str(job_id))
        else:
            extractors = db.query(ExtractorResultModel).filter_by(job_id=job_id).all()
            extractor_types = {e.extractor_type for e in extractors if not e.error_message}
            if not {"asr", "ocr", "audio"}.issubset(extractor_types):
                resumed_from = "extractors"
                from celery import chord, group
                from ytclfr.tasks.extract import run_asr, run_ocr, run_audio_classifier
                from ytclfr.tasks.align import build_timeline
                
                extractor_group = group(
                    run_asr.s(str(job_id)),
                    run_ocr.s(str(job_id)),
                    run_audio_classifier.s(str(job_id)),
                )
                chord(extractor_group)(build_timeline.s(str(job_id)))
            else:
                resumed_from = "build_timeline"
                from ytclfr.tasks.align import build_timeline
                build_timeline.delay(str(job_id))

    job.status = "pending"
    job.error_message = None
    db.commit()

    return RetryResponse(
        job_id=job_id,
        message="Job recovery initiated",
        resumed_from=resumed_from
    )
