import uuid
from typing import Any

from ytclfr.core.config import get_settings
from ytclfr.core.logging import get_logger
from ytclfr.db.models.extractor_result import ExtractorResultModel
from ytclfr.db.models.job import Job
from ytclfr.db.session import db_session
from ytclfr.ingestion.s3_storage import S3StorageError, S3StorageManager
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
    """Chord callback: receives lightweight status dicts from extractors
    and builds the unified aligned timeline.

    Phase 10 (DR-20): The extractor_results param now contains only
    lightweight status dicts (not full JSON payloads). The actual
    extractor data is fetched from the extractor_results Postgres
    table by job_id.

    Args:
        extractor_results: List of lightweight status dicts from
            the parallel group (job_id, extractor_type, status).
        job_id: String UUID of the job being processed.
    """
    job_uuid = uuid.UUID(job_id)

    # Log the lightweight chord results for observability
    for er in extractor_results:
        logger.info(
            "Chord result for job %s: type=%s status=%s",
            job_id,
            er.get("extractor_type", "unknown"),
            er.get("status", "unknown"),
        )

    with db_session() as session:
        job = session.query(Job).filter(Job.id == job_uuid).first()
        if job:
            job.status = "aligning"
            session.commit()

    # Phase 10 (DR-20): Fetch actual extractor results from Postgres
    # instead of reading from chord arguments.
    db_extractor_results = _fetch_extractor_results_from_db(job_uuid)

    # Run the alignment engine with the DB-fetched results
    from ytclfr.alignment.engine import align

    timeline = align(
        job_id=job_uuid,
        extractor_results=db_extractor_results,
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
        extractor_results=db_extractor_results,
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

    result = timeline.model_dump(mode="json")
    confidence_dict = {
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
    result["confidence_verdict"] = confidence_dict

    from ytclfr.storage.segment_store import save_aligned_segments
    from ytclfr.storage.output_store import assemble_and_save_final_output
    from ytclfr.cache.result_cache import invalidate_result
    from sqlalchemy.sql import func

    with db_session() as session:
        settings = get_settings()
        
        save_aligned_segments(job_uuid, timeline, settings, session)
        
        assemble_and_save_final_output(job_uuid, timeline, confidence_dict, session)
        
        job = session.query(Job).filter(Job.id == job_uuid).first()
        if job:
            job.status = "completed"
            job.updated_at = func.now()
            session.commit()
            
    invalidate_result(job_uuid)

    try:
        s3_manager = S3StorageManager(get_settings())
        s3_manager.delete_directory(prefix=f"{job_id}/")
    except S3StorageError as e:
        logger.error("Failed to delete S3 directory for job %s: %s", job_id, e)
    except AttributeError as e:
        # Catch AttributeError if delete_directory is not yet implemented
        logger.error(
            "S3StorageManager missing delete_directory method for job %s: %s",
            job_id,
            e,
        )

    return {"job_id": job_id, "status": "aligned_and_evaluated"}


def _fetch_extractor_results_from_db(
    job_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Fetch extractor results from Postgres for a given job.

    Queries the extractor_results table and reconstructs the
    dict format expected by the alignment engine, matching the
    ExtractorResult.model_dump(mode="json") shape that the
    pre-Phase-10 code used to pass through Redis.

    For each (job_id, extractor_type), only the latest result
    (by created_at) is used.
    """
    results: list[dict[str, Any]] = []

    with db_session() as session:
        # Get all extractor results for this job, ordered by created_at desc
        db_results = (
            session.query(ExtractorResultModel)
            .filter(ExtractorResultModel.job_id == job_id)
            .order_by(ExtractorResultModel.created_at.desc())
            .all()
        )

        # Deduplicate: keep only the latest per extractor_type
        seen_types: set[str] = set()
        for db_result in db_results:
            if db_result.extractor_type in seen_types:
                continue
            seen_types.add(db_result.extractor_type)

            # Reconstruct the dict shape expected by align()
            result_dict: dict[str, Any] = {
                "job_id": str(db_result.job_id),
                "extractor_type": db_result.extractor_type,
                "segments": db_result.segments_json.get("segments", []),
                "total_duration_seconds": db_result.total_duration_seconds,
                "error": db_result.error_message,
                "extracted_at": (
                    db_result.extracted_at.isoformat()
                    if db_result.extracted_at
                    else None
                ),
            }
            results.append(result_dict)

    logger.info(
        "Fetched %d extractor results from DB for job %s: types=%s",
        len(results),
        job_id,
        [r["extractor_type"] for r in results],
    )
    return results
