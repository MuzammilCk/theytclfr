# build.md — ytclfr V2 Full Build Plan

CURRENT STAGE: D — Taxonomy + Intent Mapping
STATUS: Not Started
(V2 Stage A — Signal Census: COMPLETE)
(V2 Stage B — Targeted Extraction: COMPLETE)
(V2 Stage C — Evidence Fusion: COMPLETE)

## How to Use This File

Each stage is broken into numbered micro-tasks.
Use the matching prompt from `stage_a_prompts.md` (and future stage prompt packs) in Antigravity.
Complete all micro-tasks in a stage before starting the next stage.
After each micro-task, update `diff.md`.

---

## Stage A — Signal Census

Goal: Replace the V1 preflight router with a lightweight probing layer that detects what signals physically exist in the video before any expensive extraction runs.

Output artifact: `SignalManifest` stored in PostgreSQL, job transitions to `stage_b_pending`.

### Micro-Tasks

| ID | Task | File(s) |
|---|---|---|
| A-1 | Define `SignalManifest` Pydantic model | `contracts/manifest.py` |
| A-2 | Add `signal_manifests` Alembic migration | `migrations/` |
| A-3 | Add `SignalManifestRepository` to storage layer | `storage/manifest_store.py` |
| A-4 | Upgrade `audio_checker.py` — VAD + music detection | `probing/audio_checker.py` |
| A-5 | Upgrade `frame_sampler.py` — motion + face + text density | `probing/frame_sampler.py` |
| A-6 | Add `metadata_probe.py` — yt-dlp metadata parser | `probing/metadata_probe.py` |
| A-7 | Write `tasks/stage_a.py` Celery task (orchestrates A-4/A-5/A-6, saves manifest) | `tasks/stage_a.py` |
| A-8 | Add SSE event types for Stage A | `contracts/events.py` |
| A-9 | Golden JSON fixture + unit tests for SignalManifest | `tests/fixtures/signal_manifest.json`, `tests/test_stage_a.py` |

---

## Stage B — Targeted Extraction — COMPLETE

Goal: Read the `SignalManifest` and dynamically build a Celery group of only the extractors needed. No extractor runs unless its signal was confirmed in Stage A.

Output artifact: Individual extractor outputs (ASR transcript, OCR text, visual events) stored in PostgreSQL, job transitions to `stage_c_pending`.

### Micro-Tasks

| ID | Task | File(s) | Status |
|---|---|---|---|
| B-1 | Add SSE event types for Stage B | `contracts/events.py` | ✅ |
| B-2 | Write `tasks/stage_b.py` — reads manifest, builds dynamic Celery group | `tasks/stage_b.py` | ✅ |
| B-3 | Wire Stage A → Stage B trigger | `tasks/stage_a.py` | ✅ |
| B-4 | Celery worker registration | `queue/celery_app.py` | ✅ |
| B-5 | Stage B unit tests | `tests/unit/stage_b/` | ✅ |

---

## Stage C — Evidence Fusion — COMPLETE
**Goal:** Merge extractor outputs into a single time-aligned evidence graph and extract semantic insights.

### Implementation Status
- [x] **C-1: Event Contracts** (`contracts/events.py`)
  - Added `StageCEvent` and `StageCStatus` (STARTED, ALIGNMENT_COMPLETE, ENTITIES_EXTRACTED, GROQ_COMPLETE, GROQ_SKIPPED, COMPLETE, FAILED).
- [x] **C-2: Evidence Contracts** (`contracts/evidence.py`)
  - Created `EvidenceGraph`, `FusedSegment`, and `ExtractedEntity` models.
- [x] **C-3: Database Models** (`db/models/evidence_graph.py`, `alembic/`)
  - Added `evidence_graphs` table with JSON columns and generated Alembic migration.
- [x] **C-4: Evidence Store** (`storage/evidence_store.py`)
  - Implemented `EvidenceGraphStore` with `upsert` and `get_by_job_id`.
- [x] **C-5: Entity Extractor** (`fusion/entity_extractor.py`)
  - Added pure heuristic extraction logic for capitalized phrases.
- [x] **C-6: Groq Reasoner** (`fusion/groq_reasoner.py`)
  - Added LLM inference for dominant subject, summaries, and scene boundaries.
- [x] **C-7: Fusion Task** (`tasks/stage_c.py`)
  - Implemented `run_fuse_evidence` Celery chord callback to replace V1 `build_timeline`.
  - Wires V1 alignment, entity extraction, and Groq reasoning.
- [x] **C-8: Celery Integration** (`tasks/stage_b.py`, `queue/celery_app.py`)
  - Updated Stage B to trigger `run_fuse_evidence` instead of `build_timeline`.
  - Registered `stage_c` with Celery app.
- [x] **C-9: Testing** (`tests/unit/stage_c/`)
  - Added comprehensive test suite with mocked Groq calls and golden JSON fixture.

---

## Stage D — Taxonomy + Intent Mapping

Goal: Use the `EvidenceGraph` to produce a final structured classification: parent category, child category, intent. This is the last step — classification happens only after evidence is complete.

Output artifact: Enriched `FinalOutput` stored in PostgreSQL, job transitions to `completed`.

### Micro-Tasks

| ID | Task | File(s) |
|---|---|---|
| D-1 | Define enriched `FinalOutput` Pydantic model | `contracts/output.py` |
| D-2 | Update `final_outputs` table (Alembic migration) | `migrations/` |
| D-3 | Write `taxonomy/mapper.py` — Groq-powered taxonomy classification | `taxonomy/mapper.py` |
| D-4 | Write `taxonomy/intent_resolver.py` — resolves intent from evidence | `taxonomy/intent_resolver.py` |
| D-5 | Write `tasks/stage_d.py` — runs mapper, saves FinalOutput | `tasks/stage_d.py` |
| D-6 | Update `storage/output_store.py` to V2 schema (remove hardcoded `content_type_map`) | `storage/output_store.py` |
| D-7 | Add SSE event types for Stage D + job completion | `contracts/events.py` |
| D-8 | Golden JSON fixtures + unit tests for Stage D | `tests/fixtures/`, `tests/test_stage_d.py` |

---

## Pipeline Wiring (After All Stages)

Once all four stages are built independently and tested, wire them into the full pipeline:

| ID | Task | File(s) |
|---|---|---|
| W-1 | Update `tasks/route.py` to trigger Stage A instead of old group | `tasks/route.py` |
| W-2 | Wire Stage A completion → Stage B trigger via Celery callback | `tasks/stage_a.py` |
| W-3 | Wire Stage B completion → Stage C trigger | `tasks/stage_b.py` |
| W-4 | Wire Stage C completion → Stage D trigger | `tasks/stage_c.py` |
| W-5 | Update job status state machine in DB | `storage/job_store.py` |
| W-6 | Update FastAPI job status endpoint to return new fields | `api/jobs.py` |
| W-7 | Integration test: full pipeline on a short test video | `tests/test_pipeline_integration.py` |

---

## Deprecation Schedule (V1 Artifacts to Remove After V2 Is Live)

| File | Action | When |
|---|---|---|
| `contracts/router.py` | Delete — replaced by `contracts/manifest.py` | After A-1 is stable |
| `router/classifier.py` | Delete — replaced by `tasks/stage_a.py` | After A-7 is stable |
| `tasks/route.py` (old body) | Gutted — only triggers Stage A now | After W-1 |
| `storage/output_store.py` `content_type_map` dict | Delete hardcoded map | After D-6 |
| `tasks/align.py` | Merged into Stage C | After C-6 |

---

## V2 Control Files Reference

All V2 control files live in `V2/`:

| File | Purpose |
|---|---|
| `V2/context.md` | Frozen stack, V2 pipeline definition, data contracts |
| `V2/claude.md` | Behavioral rules and code standards for the AI |
| `V2/build.md` | This file — stage plan and checklists |
| `V2/diff.md` | Append-only session changelog |
| `V2/decisions.md` | Decision Records (DR-V2-XX) — created in Stage A, Part C |

**Session Protocol:** Every Antigravity session starts by reading all five files. Every session ends by appending to `V2/diff.md` and, if an architectural decision was made, appending to `V2/decisions.md`.

---

## Stage A Start Checklist

Before running the Stage A prompt, verify:
- [x] PostgreSQL is running and accessible.
- [x] Redis is running.
- [x] `alembic.ini` is configured with correct `DATABASE_URL`.
- [x] `config.py` has `GROQ_API_KEY` and `OLLAMA_BASE_URL` populated.
- [x] V1 tests pass: `pytest tests/ -q` shows zero failures.
- [x] `ffprobe` is available on system PATH.
- [x] `opencv-python-headless` is installed.
- [x] `webrtcvad` and `librosa` are installed or ready to install.