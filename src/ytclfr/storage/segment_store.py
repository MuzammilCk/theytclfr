from uuid import UUID

from sqlalchemy.orm import Session

from ytclfr.contracts.alignment import AlignedTimeline
from ytclfr.core.config import Settings
from ytclfr.db.models.aligned_segment import AlignedSegmentModel
from ytclfr.storage.embeddings import generate_embeddings_batch


def save_aligned_segments(job_id: UUID, timeline: AlignedTimeline, settings: Settings, session: Session) -> int:
    texts = [seg.text for seg in timeline.segments]
    embeddings = generate_embeddings_batch(texts, settings)

    session.query(AlignedSegmentModel).filter(AlignedSegmentModel.job_id == job_id).delete()

    models = []
    for seg, emb in zip(timeline.segments, embeddings, strict=True):
        models.append(
            AlignedSegmentModel(
                job_id=job_id,
                start_seconds=seg.timestamp,
                end_seconds=seg.end_timestamp,
                text=seg.text,
                source=seg.source,
                confidence=seg.confidence,
                embedding=emb,
            )
        )

    session.add_all(models)
    session.commit()
    return len(models)
