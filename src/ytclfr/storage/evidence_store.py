import logging
from uuid import UUID

from sqlalchemy.orm import Session

from ytclfr.contracts.evidence import EvidenceGraph, ExtractedEntity, FusedSegment
from ytclfr.db.models.evidence_graph import EvidenceGraphORM

logger = logging.getLogger(__name__)


class EvidenceGraphStore:
    """Read/write operations for evidence_graphs table.

    Uses upsert pattern — one EvidenceGraph per job.
    """

    def upsert(
        self, session: Session, graph: EvidenceGraph
    ) -> EvidenceGraphORM:
        """Insert or update the EvidenceGraph for a job.

        If a record already exists for job_id, overwrite it.
        Returns the persisted ORM object.
        """
        orm = session.query(EvidenceGraphORM).filter(
            EvidenceGraphORM.job_id == graph.job_id
        ).first()

        segments_data = {"segments": [s.model_dump() for s in graph.segments]}
        entities_data = {"entities": [e.model_dump() for e in graph.entities]}
        scene_boundaries_data = {"boundaries": graph.scene_boundaries}
        modality_coverage_data = {"coverage": graph.modality_coverage}
        conflict_details_data = {"details": graph.conflict_details}
        evidence_priority_notes_data = {"notes": graph.evidence_priority_notes}

        if orm:
            orm.segments_json = segments_data
            orm.entities_json = entities_data
            orm.dominant_subject = graph.dominant_subject
            orm.groq_summary = graph.groq_summary
            orm.scene_boundaries_json = scene_boundaries_data
            orm.groq_reasoning_used = graph.groq_reasoning_used
            orm.modality_coverage_json = modality_coverage_data
            orm.conflict_count = graph.conflict_count
            orm.conflict_details_json = conflict_details_data
            orm.structural_video_type = graph.structural_video_type
            orm.evidence_priority_notes_json = evidence_priority_notes_data
            orm.primary_evidence_modality = graph.primary_evidence_modality
            orm.total_segments = graph.total_segments
            orm.confidence = graph.confidence
        else:
            orm = EvidenceGraphORM(
                job_id=graph.job_id,
                segments_json=segments_data,
                entities_json=entities_data,
                dominant_subject=graph.dominant_subject,
                groq_summary=graph.groq_summary,
                scene_boundaries_json=scene_boundaries_data,
                groq_reasoning_used=graph.groq_reasoning_used,
                modality_coverage_json=modality_coverage_data,
                conflict_count=graph.conflict_count,
                conflict_details_json=conflict_details_data,
                structural_video_type=graph.structural_video_type,
                evidence_priority_notes_json=evidence_priority_notes_data,
                primary_evidence_modality=graph.primary_evidence_modality,
                total_segments=graph.total_segments,
                confidence=graph.confidence,
            )
            session.add(orm)

        session.commit()
        session.refresh(orm)
        logger.debug("Upserted evidence graph for job %s", graph.job_id)
        return orm

    def get_by_job_id(
        self, session: Session, job_id: UUID
    ) -> EvidenceGraph | None:
        """Return EvidenceGraph for a job, or None if not found.

        Reconstructs FusedSegment and ExtractedEntity lists
        from JSON columns.
        """
        orm = session.query(EvidenceGraphORM).filter(
            EvidenceGraphORM.job_id == job_id
        ).first()

        if not orm:
            return None

        segments = [
            FusedSegment.model_validate(s)
            for s in orm.segments_json.get("segments", [])
        ]
        entities = [
            ExtractedEntity.model_validate(e)
            for e in orm.entities_json.get("entities", [])
        ]
        scene_boundaries = orm.scene_boundaries_json.get("boundaries", [])
        modality_coverage = orm.modality_coverage_json.get("coverage", {})
        conflict_details = orm.conflict_details_json.get("details", [])
        evidence_priority_notes = orm.evidence_priority_notes_json.get("notes", [])

        return EvidenceGraph(
            job_id=orm.job_id,
            segments=segments,
            entities=entities,
            dominant_subject=orm.dominant_subject,
            groq_summary=orm.groq_summary,
            scene_boundaries=scene_boundaries,
            groq_reasoning_used=orm.groq_reasoning_used,
            modality_coverage=modality_coverage,
            conflict_count=orm.conflict_count,
            conflict_details=conflict_details,
            structural_video_type=orm.structural_video_type,
            evidence_priority_notes=evidence_priority_notes,
            primary_evidence_modality=orm.primary_evidence_modality,
            total_segments=orm.total_segments,
            confidence=orm.confidence,
            created_at=orm.created_at,
        )
