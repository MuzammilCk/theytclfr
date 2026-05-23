"""Storage layer for signal_manifests table.

Read/write operations for SignalManifest persistence.
Follows existing storage patterns in the project.
No Celery, FastAPI, or task imports.
"""

import logging
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from ytclfr.contracts.manifest import SignalManifest
from ytclfr.db.models.signal_manifest import SignalManifestORM

logger = logging.getLogger(__name__)


class SignalManifestStore:
    """Read/write operations for signal_manifests table."""

    def create(
        self, session: Session, manifest: SignalManifest
    ) -> SignalManifestORM:
        """Insert a new SignalManifest record and return the ORM object.

        Args:
            session: Active SQLAlchemy session.
            manifest: Validated SignalManifest Pydantic model.

        Returns:
            The persisted SignalManifestORM instance with
            server-generated id and created_at.
        """
        orm_obj = SignalManifestORM(
            job_id=manifest.job_id,
            audio_type=manifest.audio_type,
            language=manifest.language,
            has_speech=manifest.has_speech,
            has_music=manifest.has_music,
            has_burned_in_text=manifest.has_burned_in_text,
            has_subtitle_track=manifest.has_subtitle_track,
            has_faces=manifest.has_faces,
            motion_density=manifest.motion_density,
            motion_score=manifest.motion_score,
            aspect_ratio=manifest.aspect_ratio,
            content_format=manifest.content_format,
            scene_cut_count=manifest.scene_cut_count,
            duration_seconds=manifest.duration_seconds,
            probing_confidence=manifest.probing_confidence,
        )
        session.add(orm_obj)
        session.commit()
        session.refresh(orm_obj)
        logger.debug(
            "Created signal manifest for job %s", manifest.job_id
        )
        return orm_obj

    def get_by_job_id(
        self, session: Session, job_id: UUID
    ) -> SignalManifest | None:
        """Return the SignalManifest for a job, or None if not found.

        Args:
            session: Active SQLAlchemy session.
            job_id: UUID of the job to look up.

        Returns:
            SignalManifest if found, None otherwise.
        """
        orm_obj = session.query(SignalManifestORM).filter(
            SignalManifestORM.job_id == job_id
        ).first()
        if orm_obj is None:
            return None
        return SignalManifest.model_validate(orm_obj)

    def update_confidence(
        self, session: Session, job_id: UUID, confidence: float
    ) -> None:
        """Update probing_confidence for a given job_id.

        Args:
            session: Active SQLAlchemy session.
            job_id: UUID of the job to update.
            confidence: New confidence value (0.0–1.0).
        """
        session.execute(
            update(SignalManifestORM)
            .where(SignalManifestORM.job_id == job_id)
            .values(probing_confidence=confidence)
        )
        session.commit()
