# build.md — ytclfr V2 Full Build Plan

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

## Stage B — Targeted Extraction

Goal: Read the `SignalManifest` and dynamically build a Celery group of only the extractors needed. No extractor runs unless its signal was confirmed in Stage A.

Output artifact: Individual extractor outputs (ASR transcript, OCR text, visual events) stored in PostgreSQL, job transitions to `stage_c_pending`.

### Micro-Tasks

| ID | Task | File(s) |
|---|---|---|
| B-1 | Define extractor output Pydantic models (`ASROutput`, `OCROutput`, `VisualOutput`) | `contracts/extractor_outputs.py` |
| B-2 | Add extractor output tables (Alembic migration) | `migrations/` |
| B-3 | Refactor `tasks/asr.py` to V2 contract | `tasks/asr.py` |
| B-4 | Refactor `tasks/ocr.py` to V2 contract | `tasks/ocr.py` |
| B-5 | Add `tasks/visual_extractor.py` (scene cut + face detection) | `tasks/visual_extractor.py` |
| B-6 | Write `tasks/stage_b.py` — reads manifest, builds dynamic Celery group | `tasks/stage_b.py` |
| B-7 | Add SSE event types for Stage B | `contracts/events.py` |
| B-8 | Golden JSON fixtures + unit tests for Stage B | `tests/fixtures/`, `tests/test_stage_b.py` |

---

## Stage C — Evidence Fusion

Goal: Take all extractor outputs and produce a single fused evidence graph with aligned timestamps, extracted entities, and confidence scores. LLM call via Groq to answer "what is this video about?"

Output artifact: `EvidenceGraph` stored in PostgreSQL, job transitions to `stage_d_pending`.

### Micro-Tasks

| ID | Task | File(s) |
|---|---|---|
| C-1 | Define `EvidenceGraph`, `FusedSegment`, `ExtractedEntity` Pydantic models | `contracts/evidence.py` |
| C-2 | Add `evidence_graphs` Alembic migration | `migrations/` |
| C-3 | Upgrade `alignment/engine.py` to V2 temporal alignment | `alignment/engine.py` |
| C-4 | Write `fusion/entity_extractor.py` (extracts products, people, places from transcript) | `fusion/entity_extractor.py` |
| C-5 | Write `fusion/groq_reasoner.py` (Groq API call: dominant subject + scene summary) | `fusion/groq_reasoner.py` |
| C-6 | Write `tasks/stage_c.py` — fuses all evidence, saves EvidenceGraph | `tasks/stage_c.py` |
| C-7 | Add SSE event types for Stage C | `contracts/events.py` |
| C-8 | Golden JSON fixtures + unit tests for Stage C | `tests/fixtures/`, `tests/test_stage_c.py` |

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

## Stage A Start Checklist

Before running Stage A prompts, verify:
- [ ] PostgreSQL is running and accessible.
- [ ] Redis is running.
- [ ] `alembic.ini` is configured with correct `DATABASE_URL`.
- [ ] `config.py` has `GROQ_API_KEY` and `OLLAMA_BASE_URL` populated.
- [ ] V1 tests still pass (do not break existing behavior during Stage A build).
- [ ] `ffprobe` is available on system PATH (needed for audio probing).
- [ ] `opencv-python-headless` is installed (needed for frame probing).