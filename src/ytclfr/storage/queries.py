from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from ytclfr.contracts.output import FinalOutput
from ytclfr.db.models.final_output import FinalOutputModel
from ytclfr.db.models.aligned_segment import AlignedSegmentModel
from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM


def get_final_output_by_job_id(job_id: UUID, session: Session) -> FinalOutputModel | None:
    return session.query(FinalOutputModel).filter(FinalOutputModel.job_id == job_id).first()


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


def search_v3_evidence_keyword(job_id: UUID, query: str, session: Session) -> list[dict]:
    """Keyword search over a V3 job's evidence graph segments (stored as JSON).

    V3 jobs persist fused segments in ``v3_evidence_graphs.segments_json`` rather
    than the legacy ``aligned_segments`` table, so lexical search must inspect
    that JSON payload directly.
    """
    evidence = (
        session.query(V3EvidenceGraphORM)
        .filter(V3EvidenceGraphORM.job_id == job_id)
        .first()
    )
    if not evidence:
        return []

    segments = (evidence.segments_json or {}).get("segments", [])
    needle = query.lower()
    out: list[dict] = []
    for seg in segments:
        text = seg.get("text") or ""
        if needle in text.lower():
            out.append(
                {
                    "start_seconds": seg.get("timestamp"),
                    "end_seconds": seg.get("end_timestamp"),
                    "text": text,
                    "source": seg.get("source"),
                    "confidence": seg.get("confidence"),
                }
            )
    return out
