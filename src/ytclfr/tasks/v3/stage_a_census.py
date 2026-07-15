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
from ytclfr.probing.audio_checker import probe_audio
from ytclfr.probing.frame_sampler import probe_visual
from ytclfr.probing.metadata_probe import probe_metadata_dict
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
            # v3_run_targeted_extraction already dispatches ASR and/or OCR
            # itself based on the manifest flags (see stage_b_extraction.py) —
            # do not also queue v3_run_asr directly here, or ASR runs twice.
            from ytclfr.tasks.v3.stage_b_extraction import v3_run_targeted_extraction
            v3_run_targeted_extraction.delay(job_id)
            return {"job_id": job_id, "status": "skipped"}

        s3 = S3StorageManager(settings)
        temp_dir = tempfile.mkdtemp()
        from pathlib import Path
        local_video_path = Path(temp_dir) / "video.mp4"

        try:
            s3_object_key = f"{job_id}/video.mp4"
            s3.download_file(s3_object_key, local_video_path)

            raw_meta = job.metadata_raw or {}
            if isinstance(raw_meta, str):
                import json
                raw_meta = json.loads(raw_meta)
            
            meta_res = probe_metadata_dict(raw_meta)
            audio_res = probe_audio(str(local_video_path), raw_meta)
            visual_res = probe_visual(str(local_video_path), retain_frames=True)

            is_shadow_v4 = (job_uuid.int % 10 == 0)
            
            vlm_struct_type = "none"
            overlay_density = 0.0

            if is_shadow_v4:
                meta = extract_metadata_pyav(local_video_path)
                frames = []
                for frame in visual_res.sampled_frames:
                    h, w = frame.shape[:2]
                    if w > 768:
                        new_w = 768
                        new_h = int(h * (768 / w))
                        frame = cv2.resize(frame, (new_w, new_h))
                    _, encoded = cv2.imencode('.jpg', frame)
                    frames.append(encoded.tobytes())

                vlm_result = probe_structure_vlm(frames)
                vlm_struct_type = vlm_result.get("structural_video_type", "none")
                overlay_density = vlm_result.get("overlay_text_density", 0.0)

            # Combine into manifest based on real prober returns
            manifest = SignalManifest(
                job_id=job_uuid,
                audio_type=audio_res.audio_type,
                language=audio_res.language or meta_res.language or "en",
                has_speech=audio_res.has_speech,
                has_music=audio_res.has_music,
                has_burned_in_text=visual_res.has_burned_in_text,
                has_subtitle_track=meta_res.has_subtitle_track,
                has_faces=visual_res.has_faces,
                motion_density=visual_res.motion_density,
                motion_score=visual_res.motion_score,
                aspect_ratio=visual_res.aspect_ratio,
                content_format=visual_res.content_format,
                scene_cut_count=visual_res.scene_cut_count,
                duration_seconds=meta_res.duration_seconds or audio_res.duration_seconds,
                probing_confidence=min(audio_res.confidence, visual_res.confidence),
                metadata_prior_confidence=meta_res.confidence,
                structural_score=0.5 if vlm_struct_type != "none" else 0.0,
                list_likelihood=0.8 if vlm_struct_type == "list" else 0.0,
                countdown_likelihood=0.8 if vlm_struct_type == "countdown" else 0.0,
                overlay_text_density=overlay_density,
                ordinal_pattern_score=1.0 if meta_res.metadata_structural_hints.get("title_has_ordinals") else 0.0,
                scene_repeat_score=0.0,
                ocr_required=visual_res.has_burned_in_text,
                ocr_expected_coverage=0.5 if visual_res.has_burned_in_text else 0.0,
                asr_expected_value=0.8 if audio_res.has_speech else 0.0,
                structural_video_type=vlm_struct_type,
            )

            store.create(db, manifest)
            
            # Queue extraction orchestrator
            from ytclfr.tasks.v3.stage_b_extraction import v3_run_targeted_extraction
            v3_run_targeted_extraction.delay(job_id)
            
            job.status = "v3_stage_a_complete"
            db.commit()

        except Exception as exc:
            db.rollback()
            if self.request.retries >= self.max_retries:
                try:
                    job_obj = db.query(Job).filter(Job.id == job_uuid).first()
                    if job_obj:
                        job_obj.status = "dead_letter"
                        job_obj.error_message = str(exc)
                        db.commit()
                except Exception:
                    pass
                logger.error(
                    "Stage A census exhausted all retries for job %s: %s",
                    job_id,
                    str(exc),
                )
                return {
                    "job_id": str(job_id),
                    "status": "failed",
                }
            raise self.retry(exc=exc)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return {"job_id": job_id, "status": "completed"}
