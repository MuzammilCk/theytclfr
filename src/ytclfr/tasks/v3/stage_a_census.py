import uuid
import os
import shutil
import tempfile
import cv2
from celery import shared_task
from typing import Any

from ytclfr.db.session import db_session
from ytclfr.db.models.job import Job
from ytclfr.ingestion.s3_storage import S3StorageManager
from ytclfr.probing.vlm_structural_probe import probe_structure_vlm
from ytclfr.ingestion.metadata_pyav import extract_metadata_pyav
from ytclfr.contracts.v3.manifest import SignalManifest
from ytclfr.storage.manifest_store import SignalManifestStore
from ytclfr.tasks.v3.v3_extraction_tasks import v3_run_asr
from ytclfr.core.logging import get_logger
from ytclfr.core.config import get_settings
from ytclfr.queue.celery_app import celery_app

logger = get_logger(__name__)

@celery_app.task(bind=True, name="ytclfr.tasks.v3.stage_a_census.v3_run_signal_census", queue="heavy", max_retries=3, default_retry_delay=30)
def v3_run_signal_census(self: Any, job_id: str) -> dict[str, Any]:
    job_uuid = uuid.UUID(job_id)
    settings = get_settings()

    with db_session() as db:
        job = db.query(Job).filter(Job.id == job_uuid).first()
        if not job or not job.s3_video_uri:
            raise ValueError("No video in S3 for job " + job_id)

        job.status = "v3_stage_a_running"
        db.commit()

        # Check idempotency
        store = SignalManifestStore()
        existing_manifest = store.get_by_job_id(db, job_uuid)
        if existing_manifest:
            logger.info(f"V3 Stage A idempotency hit for job {job_id}")
            v3_run_asr.delay(job_id)
            # also queue OCR / audio here if needed in v3_stage_b_extraction
            from ytclfr.tasks.v3.stage_b_extraction import v3_run_extraction_orchestrator
            v3_run_extraction_orchestrator.delay(job_id)
            return {"job_id": job_id, "status": "skipped"}

        s3 = S3StorageManager(settings)
        temp_dir = tempfile.mkdtemp()
        from pathlib import Path
        local_video_path = Path(temp_dir) / "video.mp4"

        try:
            s3_object_key = f"{job_id}/video.mp4"
            s3.download_file(s3_object_key, local_video_path)

            meta = extract_metadata_pyav(local_video_path)

            frames = []
            cap = cv2.VideoCapture(local_video_path)
            if cap.isOpened():
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if frame_count > 0:
                    step = max(1, frame_count // 5)
                    for i in range(1, 5):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, i * step)
                        ret, frame = cap.read()
                        if ret:
                            h, w = frame.shape[:2]
                            if w > 768:
                                new_w = 768
                                new_h = int(h * (768 / w))
                                frame = cv2.resize(frame, (new_w, new_h))
                            _, encoded = cv2.imencode('.jpg', frame)
                            frames.append(encoded.tobytes())
                cap.release()

            vlm_result = probe_structure_vlm(frames)
            
            # Combine into manifest
            # Use data from pyav metadata and vlm result
            audio_codec = meta.get("audio_codec")
            has_audio = audio_codec is not None
            
            # Extract VLM fields safely
            vlm_struct_type = vlm_result.get("structural_video_type", "none")
            overlay_density = vlm_result.get("overlay_text_density", 0.0)

            manifest = SignalManifest(
                job_id=job_uuid,
                audio_type="speech_only" if has_audio else "silent",
                language="en", # Defaulting for now unless pyav extracts it
                has_speech=has_audio,
                has_music=False,
                has_burned_in_text=(overlay_density > 0.1),
                has_subtitle_track=False,
                has_faces=False,  # default
                motion_density=0.5,
                motion_score=0.5,
                aspect_ratio="16:9",
                content_format="unknown",
                scene_cut_count=5,
                duration_seconds=meta.get("duration", 0.0),
                probing_confidence=0.8,
                metadata_prior_confidence=0.8,
                structural_score=0.5 if vlm_struct_type != "none" else 0.0,
                list_likelihood=0.8 if vlm_struct_type == "list" else 0.0,
                countdown_likelihood=0.8 if vlm_struct_type == "countdown" else 0.0,
                overlay_text_density=overlay_density,
                ordinal_pattern_score=0.0,
                scene_repeat_score=0.0,
                ocr_required=(overlay_density > 0.05),
                ocr_expected_coverage=overlay_density,
                asr_expected_value=0.8,
                structural_video_type=vlm_struct_type,
            )

            store.create(db, manifest)
            
            # Queue extraction orchestrator
            from ytclfr.tasks.v3.stage_b_extraction import v3_run_extraction_orchestrator
            v3_run_extraction_orchestrator.delay(job_id)
            
            job.status = "v3_stage_a_complete"
            db.commit()

        except Exception as exc:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_uuid).first()
            if job:
                job.status = "v3_stage_a_failed"
                job.error_message = str(exc)
                db.commit()
            raise self.retry(exc=exc)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return {"job_id": job_id, "status": "completed"}
