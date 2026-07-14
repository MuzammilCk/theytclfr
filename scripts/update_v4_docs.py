import datetime
import os

date_str = datetime.datetime.now().strftime('%Y-%m-%d')
diff_entry = f"""

### {date_str}: V4 Shadow Wiring & Diffing Engine Complete
Files changed: src/ytclfr/tasks/v4_shadow/shadow_orchestrator.py, src/ytclfr/queue/celery_app.py, scripts/v4_evaluate.py

Summary:
  - Created `run_v4_shadow_pipeline` Celery task to execute advanced ML modules (PyAV metadata fast extraction, ffmpeg/cv2 frame sampling, and VLM structural probing) in the background.
  - Implemented a deterministic `uuid5` hashing strategy to isolate V4's writes to `final_outputs` and avoid `UNIQUE(job_id)` database collisions with the V3 production pipeline.
  - Registered the new task in `celery_app.py` so workers can pick it up.
  - Built `v4_evaluate.py` to compare V3 taxonomy outputs against V4 VLM structural types for shadow jobs.
"""

decision_entry = f"""

## DR-V4-06 — UUID5 Shadow ID for Database Collision Avoidance
Date: {date_str}
Status: ACCEPTED
Context: The `final_outputs` table has a `UNIQUE(job_id)` constraint to enforce one final result per user submission. However, the V4 shadow pipeline processes the exact same `job_id` in parallel with V3. If V4 attempts to write its shadow result using the original `job_id`, it will trigger a Postgres `IntegrityError` and crash the Celery worker.
Decision: The V4 `shadow_orchestrator` generates a deterministic shadow job ID using `uuid.uuid5(uuid.NAMESPACE_DNS, f"{{job_id}}_v4_shadow")`. V4 saves its output using this shadow ID. The original `job_id` is preserved inside the `output_json` payload for evaluation cross-referencing.
Consequences: Enables safe, parallel writes to the `final_outputs` table without altering the existing schema or dropping the uniqueness constraint. Both V3 and V4 results coexist gracefully.
"""

build_entry = f"""
### {date_str}: Shadow Pipeline Execution Engine
- [x] V4 Celery Orchestrator (`shadow_orchestrator.py`)
- [x] Task Registration (`celery_app.py`)
- [x] Evaluation Script (`v4_evaluate.py`)
- [x] Database Collision Avoidance (`uuid5`)
"""

def append_safe(file, text):
    if os.path.exists(file):
        with open(file, 'ab') as f:
            f.write(text.encode('utf-8'))
    else:
        print(f"Warning: {file} not found.")

append_safe('diff.md', diff_entry)
append_safe('decisions.md', decision_entry)
append_safe('v2/decisions.md', decision_entry)
append_safe('build.md', build_entry)

print("V4 Documentation successfully appended.")
