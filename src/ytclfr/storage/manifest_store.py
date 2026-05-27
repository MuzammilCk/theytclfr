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
            metadata_prior_confidence=manifest.metadata_prior_confidence,
            structural_score=manifest.structural_score,
            list_likelihood=manifest.list_likelihood,
            countdown_likelihood=manifest.countdown_likelihood,
            overlay_text_density=manifest.overlay_text_density,
            ordinal_pattern_score=manifest.ordinal_pattern_score,
            scene_repeat_score=manifest.scene_repeat_score,
            ocr_required=manifest.ocr_required,
            ocr_expected_coverage=manifest.ocr_expected_coverage,
            asr_expected_value=manifest.asr_expected_value,
            structural_video_type=manifest.structural_video_type,
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

    def update_structural_scores(
        self, session: Session, job_id: UUID, ordinal_score: float, countdown_score: float
    ) -> None:
        """Update ordinal and countdown scores post-OCR.

        Args:
            session: Active SQLAlchemy session.
            job_id: UUID of the job to update.
            ordinal_score: New ordinal_pattern_score (0.0–1.0).
            countdown_score: New countdown_likelihood (0.0–1.0).
        """
        session.execute(
            update(SignalManifestORM)
            .where(SignalManifestORM.job_id == job_id)
            .values(
                ordinal_pattern_score=ordinal_score,
                countdown_likelihood=countdown_score
            )
        )
        session.commit()
