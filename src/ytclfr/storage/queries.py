from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from ytclfr.contracts.output import FinalOutput
from ytclfr.db.models.final_output import FinalOutputModel
from ytclfr.db.models.aligned_segment import AlignedSegmentModel


def get_final_output_by_job_id(job_id: UUID, session: Session) -> FinalOutput | None:
    model = session.query(FinalOutputModel).filter(FinalOutputModel.job_id == job_id).first()
    if model:
        return FinalOutput.model_validate(model.output_json)
    return None


def get_segments_by_time_range(job_id: UUID, start_sec: float, end_sec: float, session: Session) -> list[dict]:
    models = session.query(AlignedSegmentModel).filter(
        AlignedSegmentModel.job_id == job_id,
        AlignedSegmentModel.start_seconds <= end_sec,
        (AlignedSegmentModel.end_seconds >= start_sec) | (AlignedSegmentModel.end_seconds.is_(None))
    ).order_by(AlignedSegmentModel.start_seconds).all()
    
    return [
        {
            "start_seconds": m.start_seconds,
            "end_seconds": m.end_seconds,
            "text": m.text,
            "source": m.source,
            "confidence": m.confidence
        }
        for m in models
    ]


def search_segments_by_keyword(job_id: UUID, query: str, session: Session) -> list[dict]:
    models = session.query(AlignedSegmentModel).filter(
        AlignedSegmentModel.job_id == job_id,
        text("to_tsvector('english', text) @@ plainto_tsquery('english', :query)").bindparams(query=query)
    ).order_by(AlignedSegmentModel.start_seconds).all()

    return [
        {
            "start_seconds": m.start_seconds,
            "end_seconds": m.end_seconds,
            "text": m.text,
            "source": m.source,
            "confidence": m.confidence
        }
        for m in models
    ]


def search_segments_by_similarity(job_id: UUID, qvec: list[float], session: Session) -> list[dict]:
    models = session.query(AlignedSegmentModel).filter(
        AlignedSegmentModel.job_id == job_id,
        AlignedSegmentModel.embedding.is_not(None)
    ).order_by(
        AlignedSegmentModel.embedding.cosine_distance(qvec)
    ).limit(10).all()

    return [
        {
            "start_seconds": m.start_seconds,
            "end_seconds": m.end_seconds,
            "text": m.text,
            "source": m.source,
            "confidence": m.confidence
        }
        for m in models
    ]
