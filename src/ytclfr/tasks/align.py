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
        job = session.query(Job).filter(Job.id == job_uuid).first()
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
        job = session.query(Job).filter(Job.id == job_uuid).first()
        if job:
            job.status = "aligned"
            session.commit()

    logger.info(
        "Alignment complete for job %s: %d segments, has_gaps=%s",
        job_id,
        timeline.total_segments,
        timeline.has_gaps,
    )

    # Run confidence evaluation
    from ytclfr.confidence.controller import evaluate

    verdict = evaluate(
        extractor_results=extractor_results,
        aligned_timeline_dict=timeline.model_dump(mode="json"),
        current_attempt=0,  # PHASE-8-TODO: read from job metadata
    )

    logger.info(
        "Confidence verdict for job %s: overall=%.2f confident=%s should_proceed=%s",
        job_id,
        verdict.aggregate_score.overall,
        verdict.is_confident,
        verdict.should_proceed,
    )

    # PHASE-8-TODO: Persist AlignedTimeline to database.
    # PHASE-8-TODO: dispatch rescan tasks based on verdict.should_proceed

    result = timeline.model_dump(mode="json")
    result["confidence_verdict"] = {
        "overall_score": verdict.aggregate_score.overall,
        "is_confident": verdict.is_confident,
        "is_uncertain": verdict.aggregate_score.is_uncertain,
        "should_proceed": verdict.should_proceed,
        "actions": [
            {"action": a.action, "reason": a.reason}
            for a in verdict.branch_decision.actions
        ],
        "uncertainty_markers": [
            {
                "signal": m.signal_type,
                "score": m.original_score,
                "uncertain": m.is_uncertain,
                "reason": m.reason,
            }
            for m in verdict.uncertainty_markers
        ],
    }
    return result
