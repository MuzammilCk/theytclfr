import os
import shutil

ROOT_DIR = "d:/projects/ytclfr"
V2_DIR = os.path.join(ROOT_DIR, "v2")

# 1. Append to decisions.md
decisions_path = os.path.join(ROOT_DIR, "decisions.md")
with open(decisions_path, "a", encoding="utf-8") as f:
    f.write("""
---

## DR-V2-04 — Structural Metadata is a Weak Prior, Video Structure is Inferred
Date: 2026-05-26
Status: ACCEPTED
Context: Initially, metadata (like channel names or video titles) was considered enough to dictate structural taxonomy. However, a mature system should infer structure directly from the media (OCR, ASR) and treat metadata as a cheap prior.
Decision: Structural mapping is late-bound. Stage C fuses OCR, ASR, and visual evidence to confidently detect structural types (e.g., list, ranking, compilation). Stage D then uses these structural types as hard overrides for taxonomy classification, instead of relying purely on metadata.
Consequences: Requires OCR to be prioritized when structure is likely. Conflict resolver favors OCR for structured videos and ASR for non-structured speech-heavy videos.
Supersedes: NONE
""")

# 2. Append to diff.md
diff_path = os.path.join(ROOT_DIR, "diff.md")
with open(diff_path, "a", encoding="utf-8") as f:
    f.write("""
## Session 28 — V2 Stage C & D: Evidence Fusion and Taxonomy Mapping
Date: 2026-05-26
Changes:
- Implemented Evidence Fusion (Stage C) including temporal alignment of multimodal evidence.
- Created `EvidenceGraph` Pydantic models and updated Alembic migrations for JSON persistence.
- Added conflict resolution for ASR vs OCR priority depending on structural likelihood.
- Modified Groq prompt in `fusion/groq_reasoner.py` to accept structural context.
- Implemented Taxonomy Mapping (Stage D) with structural overrides.
- Updated `taxonomy/mapper.py` and `taxonomy/intent_resolver.py` to handle structural fallbacks (e.g., list, ranking, compilation).
- Updated `tasks/stage_d.py` to pull `structural_video_type` from `EvidenceGraph` and pass to taxonomy classifiers.
- Finalized V2 pipeline execution logic and taxonomy persistence in `final_outputs`.
Bugs found (not fixed):
- NONE
Scope creep rejected:
- Avoided polling or looping over Celery tasks directly, favoring the existing event-driven chord structure.
Next session must start by:
- Writing unit tests for structural detection and conflict resolution.
""")

# 3. Update build.md (mark B, C, D as complete)
build_path = os.path.join(ROOT_DIR, "build.md")
with open(build_path, "r", encoding="utf-8") as f:
    build_content = f.read()

# Replace checkboxes
build_content = build_content.replace("Status: [ ] In Progress\n\nBuild:\n  [ ] B-1", "Status: [x] Complete\n\nBuild:\n  [x] B-1")
build_content = build_content.replace("[ ] B-", "[x] B-")
build_content = build_content.replace("Status: [ ] Planned\n\nBuild:\n  [ ] C-1", "Status: [x] Complete\n\nBuild:\n  [x] C-1")
build_content = build_content.replace("[ ] C-", "[x] C-")
build_content = build_content.replace("Status: [ ] Planned\n\nBuild:\n  [ ] D-1", "Status: [x] Complete\n\nBuild:\n  [x] D-1")
build_content = build_content.replace("[ ] D-", "[x] D-")
build_content = build_content.replace("CURRENT PHASE: V2 Stage B — Targeted Extraction\nSTATUS: IN PROGRESS", "CURRENT PHASE: V2 Stage D — Taxonomy + Intent Mapping\nSTATUS: COMPLETE")
build_content = build_content.replace("CURRENT PHASE: V2 Stage B", "CURRENT PHASE: V2 Stage D")

with open(build_path, "w", encoding="utf-8") as f:
    f.write(build_content)

# 4. Synchronize to v2/
os.makedirs(V2_DIR, exist_ok=True)
for file in ["build.md", "context.md", "decisions.md", "diff.md"]:
    src = os.path.join(ROOT_DIR, file)
    dst = os.path.join(V2_DIR, file)
    if os.path.exists(src):
        shutil.copy2(src, dst)

print("Docs synchronized successfully.")
