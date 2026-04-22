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

    # Run the alignment engine
    from ytclfr.alignment.engine import align

    timeline = align(
        job_id=job_uuid,
        extractor_results=extractor_results,
    )

    # Update job status to aligned
    with db_session() as session:
        job = session.query(Job).filter(
            Job.id == job_uuid
        ).first()
        if job:
            job.status = "aligned"
            session.commit()

    logger.info(
        "Alignment complete for job %s: %d segments, has_gaps=%s",
        job_id,
        timeline.total_segments,
        timeline.has_gaps,
    )

    # PHASE-8-TODO: Persist AlignedTimeline to database.

    return timeline.model_dump(mode="json")
