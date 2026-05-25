# diff.md — ytclfr V2 Change Log

## V2 Control File Set

Files live in `V2/`. The Stage A prompt (Part C) creates `decisions.md` as the fifth file.

| File | Status |
|---|---|
| `V2/context.md` | Created — project context and frozen stack |
| `V2/claude.md` | Created — AI behavioral rules |
| `V2/build.md` | Created — stage plan and checklists |
| `V2/diff.md` | Created — this file |
| `V2/decisions.md` | **Created in Stage A Part C** — DR-V2-01, 02, 03 |

```
### [TASK-ID] — [Title]
**Date:** YYYY-MM-DD
**Files:**
- `path/to/file.py` — [created | modified | deleted]
**Summary:** One sentence describing what changed and why.
```

Keep entries in chronological order. Never edit a past entry.

---

## V1 → V2 Architectural Summary

| Component | V1 | V2 | Status |
|---|---|---|---|
| `contracts/router.py` | `RouterDecisionModel` — single early label | DEPRECATED | Pending deletion after A-1 |
| `contracts/manifest.py` | Does not exist | `SignalManifest` — multi-signal evidence object | Pending A-1 |
| `router/classifier.py` | Heuristic keyword guesser | DEPRECATED | Pending deletion after A-7 |
| `tasks/route.py` | Fires all extractors blindly | Gutted: only triggers Stage A | Pending W-1 |
| `tasks/stage_a.py` | Does not exist | Signal Census orchestrator | Pending A-7 |
| `tasks/stage_b.py` | Does not exist | Dynamic extraction group builder | Pending B-6 |
| `tasks/stage_c.py` | Does not exist | Evidence fusion + Groq reasoner | Pending C-6 |
| `tasks/stage_d.py` | Does not exist | Taxonomy + intent mapper | Pending D-5 |
| `tasks/align.py` | Basic interval merge | Merged into Stage C fusion | Pending C-6 |
| `probing/audio_checker.py` | Reads codec metadata only | VAD + music detection | Pending A-4 |
| `probing/frame_sampler.py` | Pulls 5 static frames | Motion score + face + text density | Pending A-5 |
| `probing/metadata_probe.py` | Does not exist | yt-dlp metadata + subtitle track parser | Pending A-6 |
| `storage/output_store.py` | Hardcoded `content_type_map` | Removed map, accepts rich `FinalOutput` | Pending D-6 |
| `contracts/output.py` | `content_type: str` field | Full taxonomy + evidence + provenance | Pending D-1 |
| `alignment/engine.py` | Basic timestamp math | V2 temporal alignment with confidence | Pending C-3 |
| `fusion/` directory | Does not exist | Evidence fusion layer | Pending C-4/C-5 |
| `taxonomy/` directory | Does not exist | Taxonomy + intent mapping layer | Pending D-3/D-4 |

---

## Change Entries

<!-- Append entries below this line after each micro-task -->

### A-1 — SignalManifest Pydantic Model
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/contracts/manifest.py` — created
**Summary:** Pure Pydantic v2 data contract for Stage A output. Validators enforce probing_confidence (0–1), motion_score (0–1), duration_seconds (≥0). No DB/Celery/API imports.

### A-2 — Alembic Migration: signal_manifests table
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/db/models/signal_manifest.py` — created
- `src/ytclfr/db/models/__init__.py` — modified (added SignalManifestORM)
- `alembic/env.py` — modified (added signal_manifest import)
- `alembic/versions/6c08e88f31be_add_signal_manifests.py` — created
**Summary:** ORM model and migration for signal_manifests table with FK to jobs. Cleaned autogenerate output to remove spurious drops of existing V1 indexes. Migration applied successfully.

### A-3 — SignalManifestStore
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/storage/manifest_store.py` — created
**Summary:** Repository class with create, get_by_job_id, and update_confidence methods. Follows existing storage patterns.

### A-4 — Audio Checker (VAD + Music Detection)
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/probing/__init__.py` — created
- `src/ytclfr/probing/audio_checker.py` — created
**Summary:** Full audio probe with webrtcvad VAD, librosa music detection, ffprobe metadata. Windows-compatible threading timeout (DR-V2-03). All thresholds are TUNABLE constants. Never raises.

### A-5 — Frame Sampler (Visual Probe)
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/probing/frame_sampler.py` — created
**Summary:** Visual probe with OpenCV: motion scoring, scene cut detection, Haar cascade face detection, burned-in text heuristic, content format classification. Threading timeout. Never raises.

### A-6 — Metadata Probe
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/probing/metadata_probe.py` — created
**Summary:** Parses yt-dlp .info.json for duration, aspect ratio, subtitles, chapters, tags. Zero ML, zero subprocesses. Raises FileNotFoundError/ValueError; caller handles.

### A-7 — Stage A Celery Task
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/tasks/stage_a.py` — created
**Summary:** Orchestrating task: probes metadata/audio/visual, merges into SignalManifest, persists via store. SSE events at each step via Redis pub/sub. Idempotent. Max 2 retries. STAGE-B-TODO for downstream trigger.

### A-8 — Stage A SSE Events
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/contracts/events.py` — modified
**Summary:** Added StageAStatus enum (6 statuses) and StageAEvent Pydantic model. All V1 event types preserved. Added Field import.

### A-9 — Golden Fixture + Unit Tests
**Date:** 2026-05-23
**Files:**
- `tests/fixtures/signal_manifest_golden.json` — created
- `tests/unit/stage_a/__init__.py` — created
- `tests/unit/stage_a/test_contracts.py` — created
- `tests/unit/stage_a/test_metadata_probe.py` — created
- `tests/unit/stage_a/test_audio_probe.py` — created
- `tests/unit/stage_a/test_stage_a_events.py` — created
**Summary:** 27 unit tests covering SignalManifest validation, metadata probe edge cases, audio probe mocking, and SSE event contracts. All tests pass.

### V1 Baseline Note
**Date:** 2026-05-23
**Summary:** V1 tests: 209 passed, 1 skipped, 3 pre-existing integration errors in tests/integration/test_chaos.py (missing db_session fixture — not related to V2 changes). No V1 fixes needed.

### SCOPE REVIEW Notes
- **webrtcvad-wheels** — Required for VAD in audio_checker.py. Installed via `webrtcvad-wheels` (pre-built Windows wheel) since `webrtcvad` requires C compilation unavailable on system.
- **librosa** — Required for beat tracking and spectral centroid music detection in audio_checker.py.
- Both packages are explicitly required by the Stage A build plan and V2/build.md checklist.

### V2/decisions.md Created
**Date:** 2026-05-23
**Files:**
- `V2/decisions.md` — created
**Summary:** Three decision records: DR-V2-01 (Evidence-Based Late Binding), DR-V2-02 (pure function probers), DR-V2-03 (Windows threading timeout).

### FIX-01 — Celery task registration for stage_a
**Date:** 2026-05-24
**Files:**
- `src/ytclfr/queue/celery_app.py` — modified
**Summary:** Added `import ytclfr.tasks.stage_a` to the Celery worker task registration block. Without this, run_signal_census is not registered in the worker registry and any .delay() call raises a KeyError at runtime. This is a zero-risk, one-line fix.
**Issue resolved:** Audit Issue 3 — Celery Task Registration Omission.

### FIX-02 — Thread-safe visual probing in frame_sampler.py
**Date:** 2026-05-24
**Files:**
- `src/ytclfr/probing/frame_sampler.py` — modified
**Summary:** Removed module-level _partial_result global variable and all global/assignment uses. Replaced _check_timeout() exception pattern with inline timeout_event.is_set() checks that return VisualProbeResult built from stack-local variables. Added _partial() nested helper inside _probe_visual_inner for DRY partial-state construction. Removed _TimeoutError class, _check_timeout function, and the except _TimeoutError branch in probe_visual (all dead code after the refactor). The public API (probe_visual signature and VisualProbeResult fields) is unchanged. All TUNABLE constants preserved.
**Issue resolved:** Audit Issue 4 — Global State Thread-Safety Risk.

### FIX-03 — Dict-based metadata probe (eliminate .info.json dep)
**Date:** 2026-05-24
**Files:**
- `src/ytclfr/probing/metadata_probe.py` — modified (added probe_metadata_dict function)
- `src/ytclfr/tasks/stage_a.py` — modified (Step 5 replaced with dict-based probe; metadata_json_path line removed from Step 4; probe_metadata_dict added to imports)
**Summary:** VideoDownloader never writes a .info.json file (no writeinfojson option). Even if it did, Phase 10 deletes the local directory before Stage A runs. The yt-dlp metadata dict is already available in job.metadata_raw (PostgreSQL). Added probe_metadata_dict(data: dict) as a pure dict-based parser. Updated stage_a.py Step 5 to use job.metadata_raw directly. The original probe_metadata(path) is preserved for unit tests.
**Issue resolved:** Audit Issue 2 — Metadata File-on-Disk Fallacy.

### FIX-04 — S3-aware media path resolution in stage_a.py
**Date:** 2026-05-24
**Files:**
- `src/ytclfr/tasks/stage_a.py` — modified
**Summary:** Stage A Step 4 previously read job.local_media_path directly, which is None after Phase 10 ingestion (video is in S3, local dir is deleted). Added S3 fallback: if local path is absent or missing, download from S3 to a transient scratch file (video_probe.mp4) using TempStorageManager and S3StorageManager, matching the existing pattern in tasks/extract.py. Added a finally block that deletes the transient file unconditionally, using unlink(missing_ok=True) on the specific file only (not cleanup_job, per Phase 10 bugfix pattern). Added Path, S3StorageManager, TempStorageManager imports.
**Issue resolved:** Audit Issue 1 — S3/Distributed Media Transport Coupling Gap.


### B-1 — Stage B SSE Events
**Date:** 2026-05-24
**Files:**
- `src/ytclfr/contracts/events.py` — modified
**Summary:** Added StageBStatus enum (5 statuses: STARTED, MANIFEST_LOADED, GROUP_BUILT, DISPATCHED, FAILED) and StageBEvent Pydantic v2 model with extractors_dispatched field. All V1 and Stage A events preserved intact.

### B-2 — tasks/stage_b.py: run_targeted_extraction
**Date:** 2026-05-24
**Files:**
- `src/ytclfr/tasks/stage_b.py` — created
**Summary:** Celery task on fast queue. Reads SignalManifest from DB, calls _build_extractor_names to determine dynamic extractor set, fires chord(group(*))(build_timeline.s(job_id)). Idempotent: skips if job already in post-Stage-B status. SSE at every transition. STAGE-C-TODO marks build_timeline as placeholder. _build_extractor_names is a pure function for isolated testing.

### B-3 — Wire Stage A → Stage B (tasks/stage_a.py)
**Date:** 2026-05-24
**Files:**
- `src/ytclfr/tasks/stage_a.py` — modified
**Summary:** Replaced the STAGE-B-TODO comment at Step 11 with a lazy import + run_targeted_extraction.delay(job_id) call. Stage A now triggers Stage B automatically on completion.

### B-4 — Celery registration for stage_b
**Date:** 2026-05-24
**Files:**
- `src/ytclfr/queue/celery_app.py` — modified
**Summary:** Added import ytclfr.tasks.stage_b to the worker registration block so run_targeted_extraction is discoverable by Celery workers at startup.

### B-5 — Stage B unit tests
**Date:** 2026-05-24
**Files:**
- `tests/unit/stage_b/__init__.py` — created
- `tests/unit/stage_b/test_stage_b_events.py` — created
- `tests/unit/stage_b/test_extractor_selection.py` — created
**Summary:** 5 SSE event tests and 7 extractor selection tests. All test _build_extractor_names pure function against the golden fixture. No Celery or DB mocking required. All tests pass.

### C-1 — Stage C SSE Events
Date: 2026-05-25
Files:
- `src/ytclfr/contracts/events.py` — modified
Summary: Added StageCStatus (7 values: STARTED, ALIGNMENT_COMPLETE,
  ENTITIES_EXTRACTED, GROQ_COMPLETE, GROQ_SKIPPED, COMPLETE, FAILED)
  and StageCEvent model with evidence_graph_id field. All V1 and
  Stage A/B events preserved intact.

### C-2 — EvidenceGraph Data Contracts
Date: 2026-05-25
Files:
- `src/ytclfr/contracts/evidence.py` — created
Summary: Defines FusedSegment, ExtractedEntity, EvidenceGraph Pydantic
  v2 models. EvidenceGraph is the single output of Stage C and the
  input for Stage D. confidence field_validator enforces 0.0–1.0.

### C-3 — Alembic Migration + ORM for evidence_graphs
Date: 2026-05-25
Files:
- `src/ytclfr/db/models/evidence_graph.py` — created
- `alembic/versions/00328acb33af_add_evidence_graphs.py` — created
- `alembic/env.py` — modified (added evidence_graph import)
Summary: evidence_graphs table with UNIQUE index on job_id (one
  per job). Supports upsert pattern. JSON columns for segments,
  entities, and scene_boundaries.

### C-4 — EvidenceGraphStore
Date: 2026-05-25
Files:
- `src/ytclfr/storage/evidence_store.py` — created
Summary: Repository with upsert() and get_by_job_id() methods.
  Follows manifest_store.py patterns. Reconstructs Pydantic models
  from JSON columns on read.

### C-5 — fusion/ module: entity_extractor.py
Date: 2026-05-25
Files:
- `src/ytclfr/fusion/__init__.py` — created
- `src/ytclfr/fusion/entity_extractor.py` — created
Summary: Pure function extract_entities_from_timeline(). Regex-based
  capitalized phrase extraction. All thresholds are TUNABLE constants.
  Filters stop-words. Never raises. Returns at most
  MAX_ENTITIES_RETURNED entities sorted by confidence.

### C-6 — fusion/ module: groq_reasoner.py
Date: 2026-05-25
Files:
- `src/ytclfr/fusion/groq_reasoner.py` — created
Summary: Pure function reason_over_evidence(). Calls Groq API via
  httpx with json_object response format. Degrades gracefully on
  missing API key, network failure, or malformed response (all return
  reasoning_used=False). Prompt is capped at MAX_TRANSCRIPT_CHARS.
  Never raises to caller.

### C-7 — tasks/stage_c.py: run_fuse_evidence
Date: 2026-05-25
Files:
- `src/ytclfr/tasks/stage_c.py` — created
Summary: Celery chord callback on fast queue that replaces
  build_timeline for V2 jobs. Runs V1 align() + save_aligned_segments
  for backward compat, then entity extraction, Groq reasoning,
  EvidenceGraph construction + persistence. Sets job to
  stage_c_complete. Cleans up S3 directory. STAGE-D-TODO comment
  marks where Stage D trigger will go.

### C-8 — Wire Stage B → Stage C
Date: 2026-05-25
Files:
- `src/ytclfr/tasks/stage_b.py` — modified
- `src/ytclfr/queue/celery_app.py` — modified
Summary: Stage B now calls chord(group)(run_fuse_evidence.s(job_id))
  instead of build_timeline.s(). Lazy import inside function body.
  celery_app.py registers ytclfr.tasks.stage_c.

### C-9 — Stage C unit tests
Date: 2026-05-25
Files:
- `tests/fixtures/evidence_graph_golden.json` — created
- `tests/unit/stage_c/__init__.py` — created
- `tests/unit/stage_c/test_evidence_contracts.py` — created
- `tests/unit/stage_c/test_entity_extractor.py` — created
- `tests/unit/stage_c/test_groq_reasoner.py` — created
- `tests/unit/stage_c/test_stage_c_events.py` — created
Summary: 7 contract tests, 7 entity extractor tests, 5 Groq reasoner
  tests (httpx mocked), 5 SSE event tests. All pass.

### D-1 — Stage D SSE Events
Date: 2026-05-25
Files:
- `src/ytclfr/contracts/events.py` — modified
Summary: Added StageDStatus (6 values: STARTED, EVIDENCE_LOADED, GROQ_TAXONOMY_COMPLETE, GROQ_TAXONOMY_SKIPPED, COMPLETE, FAILED) and StageDEvent model with taxonomy dict field. All prior events preserved intact.

### D-2 — V2 Output Data Contracts
Date: 2026-05-25
Files:
- `src/ytclfr/contracts/v2_output.py` — created
Summary: TaxonomyResult (frozen, all taxonomy fields including groq_taxonomy_used flag), ExtractedItem (frozen, name/type/timestamp/confidence), V2FinalOutput (taxonomy + summary + items + evidence_graph_summary + provenance + confidence + fallback_notes). confidence field_validator enforces 0.0–1.0.

### D-3 — taxonomy/ package: mapper.py
Date: 2026-05-25
Files:
- `src/ytclfr/taxonomy/__init__.py` — created
- `src/ytclfr/taxonomy/mapper.py` — created
Summary: Pure function classify_taxonomy(). Groq API via httpx, json_object response format. Degrades to intent_resolver fallback on missing key/network error/malformed JSON. Never raises. VALID_PARENT_CATEGORIES set enforces valid taxonomy output.

### D-4 — taxonomy/ package: intent_resolver.py
Date: 2026-05-25
Files:
- `src/ytclfr/taxonomy/intent_resolver.py` — created
Summary: Pure function resolve_by_rules(). SUBJECT_KEYWORD_MAP with 30+ entries maps lowercase subject keywords to (parent, child, intent) tuples. Signal-based defaults for music-only, speech-only, no-signal cases. Returns TaxonomyFallback. Never raises.

### D-5 — tasks/stage_d.py: run_taxonomy_mapping
Date: 2026-05-25
Files:
- `src/ytclfr/tasks/stage_d.py` — created
Summary: Terminal V2 pipeline task on fast queue. Reads EvidenceGraph, loads SignalManifest for signal context, calls classify_taxonomy, maps entities to ExtractedItems, assembles V2FinalOutput, upserts to final_outputs with content_type="v2_"+parent_category. Sets job to "completed". Idempotent: skips if V2 record exists. PIPELINE-WIRING-TODO at Step 14 for API update (W-6).

### D-6 — Wire Stage C → Stage D
Date: 2026-05-25
Files:
- `src/ytclfr/tasks/stage_c.py` — modified
- `src/ytclfr/queue/celery_app.py` — modified
Summary: STAGE-D-TODO in stage_c.py Step 13 replaced with lazy import + run_taxonomy_mapping.delay(job_id). celery_app.py registers ytclfr.tasks.stage_d.

### D-7 — Stage D unit tests
Date: 2026-05-25
Files:
- `tests/fixtures/v2_final_output_golden.json` — created
- `tests/unit/stage_d/__init__.py` — created
- `tests/unit/stage_d/test_v2_output_contracts.py` — created (6 tests)
- `tests/unit/stage_d/test_taxonomy_mapper.py` — created (6 tests)
- `tests/unit/stage_d/test_intent_resolver.py` — created (8 tests)
- `tests/unit/stage_d/test_stage_d_events.py` — created (6 tests)
Summary: 26 total tests. Contract validation, taxonomy mapper with Groq mocking, rule-based resolver keyword coverage, SSE event contracts. All tests pass.
