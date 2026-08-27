from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ytclfr.contracts.output import FinalOutput, ListItem, ScriptSegment
from ytclfr.contracts.alignment import AlignedTimeline
from ytclfr.db.models.final_output import FinalOutputModel
from ytclfr.db.models.router_decision import RouterDecisionModel
from ytclfr.db.models.job import Job


def assemble_and_save_final_output(job_id: UUID, timeline: AlignedTimeline, confidence_verdict: dict, session: Session) -> FinalOutput:
    router_decision = session.query(RouterDecisionModel).filter(RouterDecisionModel.job_id == job_id).first()
    primary_route = router_decision.primary_route if router_decision else "mixed"
    
    job = session.query(Job).filter(Job.id == job_id).first()

    content_type_map = {
        "speech-heavy": "script",
        "list-edit": "movie_list",
        "slide-presentation": "mixed",
        "music-heavy": "mixed",
        "mixed": "mixed",
    }
    content_type = content_type_map.get(primary_route, "mixed")

    # PHASE-9-TODO: replace items with LLM-structured items.
    list_items = []
    script_items = []
    prov_list = []
    
    for seg in timeline.segments:
        prov_list.append({"start_seconds": seg.timestamp, "end_seconds": seg.end_timestamp, "source": seg.source})
        if content_type == "script":
            script_items.append(ScriptSegment(timestamp=seg.timestamp, end_timestamp=seg.end_timestamp, text=seg.text, confidence=seg.confidence))
        else:
            list_items.append(ListItem(title=seg.text, timestamp=seg.timestamp, confidence=seg.confidence))

    overall_confidence = confidence_verdict.get("overall_score", 0.0)
    
    video_meta = {}
    if job:
        video_meta = {
            "title": job.video_title if job.video_title else "Unknown",
            "channel": job.channel_name if job.channel_name else "Unknown",
            "duration": job.duration_seconds if job.duration_seconds else 0.0,
            "thumbnail_url": job.thumbnail_url if job.thumbnail_url else ""
        }

    output = FinalOutput(
        job_id=job_id,
        content_type=content_type, # type: ignore
        video_metadata=video_meta,
        items=list_items if content_type != "script" else None,
        script=script_items if content_type == "script" else None,
        confidence=overall_confidence,
        provenance=prov_list,
        processed_at=datetime.now(timezone.utc),
        processing_duration_seconds=0.0
    )
    
    # Validate via model_validate
    validated_output = FinalOutput.model_validate(output.model_dump())

    # Upsert logic
    existing = session.query(FinalOutputModel).filter(FinalOutputModel.job_id == job_id).first()
    if existing:
        existing.content_type = content_type
        existing.overall_confidence = overall_confidence
        existing.output_json = validated_output.model_dump(mode="json")
    else:
        new_model = FinalOutputModel(
            job_id=job_id,
            content_type=content_type,
            overall_confidence=overall_confidence,
            output_json=validated_output.model_dump(mode="json"),
        )
        session.add(new_model)
    
    session.commit()
    return validated_output
