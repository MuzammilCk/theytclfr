import uuid
from ytclfr.db.session import db_session
from ytclfr.db.models.job import Job
from ytclfr.tasks.align import _fetch_extractor_results_from_db
from ytclfr.alignment.engine import align
from ytclfr.confidence.controller import evaluate
from ytclfr.storage.segment_store import save_aligned_segments
from ytclfr.storage.output_store import assemble_and_save_final_output
from ytclfr.core.config import get_settings

job_id_str = "f92bc906-f1aa-4e2a-a914-8175b838bd27"
job_uuid = uuid.UUID(job_id_str)

print("Fetching extractor results...")
db_extractor_results = _fetch_extractor_results_from_db(job_uuid)

print("Aligning...")
timeline = align(job_id=job_uuid, extractor_results=db_extractor_results)

print("Evaluating...")
verdict = evaluate(
    extractor_results=db_extractor_results,
    aligned_timeline_dict=timeline.model_dump(mode="json"),
    current_attempt=0,
)

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

print("Saving aligned segments...")
with db_session() as session:
    settings = get_settings()
    save_aligned_segments(job_uuid, timeline, settings, session)

print("Assembling and saving final output...")
with db_session() as session:
    assemble_and_save_final_output(job_uuid, timeline, confidence_dict, session)

print("Done.")
