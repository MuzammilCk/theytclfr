import uuid
from typing import Any

from ytclfr.core.logging import get_logger
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.queue.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(  # type: ignore
    name="ytclfr.align.build_timeline",
    queue="fast",
)
def build_timeline(
    extractor_results: list[dict[str, Any]],
    job_id: str,
) -> dict[str, object]:
    """Chord callback: receives all extractor results
    and builds the unified aligned timeline.

    In Phase 5, this is a stub that logs receipt and
    updates job status to "aligning". The full
    temporal alignment logic is implemented in Phase 6.

    Args:
        extractor_results: List of serialized
          ExtractorResult dicts from the parallel group.
        job_id: String UUID of the job being processed.
    """
    job_uuid = uuid.UUID(job_id)

    with db_session() as session:
        job = session.query(Job).filter(
            Job.id == job_uuid
        ).first()
        if job:
            job.status = "aligning"
            session.commit()

    logger.info(
        "Alignment chord callback received %d extractor results "
        "for job %s. Full alignment deferred to Phase 6.",
        len(extractor_results),
        job_id,
    )

    # PHASE-6-TODO: Build unified aligned timeline here.

    return {
        "job_id": job_id,
        "status": "aligning",
        "extractor_count": len(extractor_results),
    }
