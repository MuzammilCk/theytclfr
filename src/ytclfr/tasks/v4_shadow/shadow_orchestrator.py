import uuid
import os
import shutil
import tempfile
from celery import shared_task
import cv2

from ytclfr.db.base import db_session
from ytclfr.db.models.job import JobModel
from ytclfr.db.models.final_output import FinalOutputModel
from ytclfr.ingestion.s3_storage import S3StorageManager
from ytclfr.probing.vlm_structural_probe import probe_structure_vlm
from ytclfr.probing.metadata_pyav import extract_metadata_fast

@shared_task(queue="heavy")
def run_v4_shadow_pipeline(job_id: str):
    # Generate deterministic shadow ID
    shadow_job_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{job_id}_v4_shadow")
    
    with db_session() as db:
        # Fetch Job
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job or not job.s3_video_uri:
            return "No video in S3"
        
        # Download video
        s3 = S3StorageManager()
        temp_dir = tempfile.mkdtemp()
        local_video_path = os.path.join(temp_dir, "video.mp4")
        
        try:
            s3.download_file(job.s3_video_uri, local_video_path)
            
            # Fast Metadata
            meta = extract_metadata_fast(local_video_path)
            
            # Extract 4 frames evenly
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
                            # Resize to max 768px width
                            h, w = frame.shape[:2]
                            if w > 768:
                                new_w = 768
                                new_h = int(h * (768 / w))
                                frame = cv2.resize(frame, (new_w, new_h))
                            # Encode to JPEG
                            _, encoded = cv2.imencode('.jpg', frame)
                            frames.append(encoded.tobytes())
                cap.release()
                
            # Run VLM probe
            vlm_result = probe_structure_vlm(frames)
            
            # Save record
            existing = db.query(FinalOutputModel).filter(FinalOutputModel.job_id == shadow_job_id).first()
            if not existing:
                output = FinalOutputModel(
                    job_id=shadow_job_id,
                    content_type="shadow_test",
                    pipeline_version="v4",
                    schema_version=2,
                    output_json={
                        "original_job_id": job_id,
                        "vlm_result": vlm_result.model_dump() if hasattr(vlm_result, 'model_dump') else vlm_result,
                        "pyav_metadata": meta.model_dump() if hasattr(meta, 'model_dump') else meta
                    }
                )
                db.add(output)
                db.commit()
                
        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    return str(shadow_job_id)
