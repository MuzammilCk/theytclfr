import sys
import json
from ytclfr.db.base import SessionLocal
from ytclfr.db.models.final_output import FinalOutputModel
from ytclfr.db.models.job import JobModel

def evaluate_shadow():
    db = SessionLocal()
    try:
        v4_outputs = db.query(FinalOutputModel).filter(FinalOutputModel.pipeline_version == 'v4').all()
        analyzed = 0
        for v4_out in v4_outputs:
            v4_json = v4_out.output_json
            orig_job_id = v4_json.get("original_job_id")
            if not orig_job_id:
                continue
            
            v3_out = db.query(FinalOutputModel).filter(
                FinalOutputModel.job_id == orig_job_id,
                FinalOutputModel.pipeline_version == 'v3'
            ).first()
            
            job = db.query(JobModel).filter(JobModel.id == orig_job_id).first()
            title = job.metadata_json.get("title", "Unknown Title") if job and job.metadata_json else "Unknown Title"
            
            v3_tax = v3_out.content_type if v3_out else "None"
            v4_type = v4_json.get("vlm_result", {}).get("structural_video_type", "Unknown")
            
            print(f"Job: {orig_job_id} | Title: {title}")
            print(f"  V3 Taxonomy: {v3_tax}")
            print(f"  V4 Structure: {v4_type}")
            print("-" * 50)
            analyzed += 1
            
        print(f"Total Shadow Jobs Analyzed: {analyzed}")
    finally:
        db.close()

if __name__ == "__main__":
    evaluate_shadow()
