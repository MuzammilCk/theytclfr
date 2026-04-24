import typing

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ytclfr.api.auth import require_auth
from ytclfr.db.models.job import Job
from ytclfr.db.session import get_db

router = APIRouter()

@router.get("/metrics")
def get_metrics(
    db: Session = Depends(get_db),
    _token: typing.Any = Depends(require_auth),
) -> dict[str, typing.Any]:
    total_jobs = db.query(Job).count()
    
    status_counts_rows = db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    status_counts = {status: count for status, count in status_counts_rows}
    
    avg_processing_time = db.query(
        func.extract('epoch', func.avg(Job.updated_at - Job.created_at))
    ).filter(Job.status == 'completed').scalar()
    
    return {
        "total_jobs": total_jobs,
        "status_counts": status_counts,
        "average_processing_time_seconds": avg_processing_time if avg_processing_time is not None else 0.0
    }
