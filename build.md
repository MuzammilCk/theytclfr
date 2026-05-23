# build.md

CURRENT PHASE: V2 Stage B — Targeted Extraction
STATUS: IN PROGRESS
(Phase 0 — Project Constitution: COMPLETE)
(Phase 1 — Data Contracts + Schemas: COMPLETE)
(Phase 2 — Ingestion + Temporary Storage: COMPLETE)
(Phase 3 — Authentication Layer: COMPLETE)
(Phase 4 — Preflight Router: COMPLETE)
(Phase 5 — Worker Queue + Parallel Extractor Infrastructure: COMPLETE)
(Phase 6 — Temporal Alignment Layer: COMPLETE)
(Phase 7 — Confidence Controller: COMPLETE)
(Phase 8 — Storage + Output API: COMPLETE)
(Phase 9 — End-to-End Hardening: COMPLETE)
(Phase 10 — V2 Distributed Scaling: COMPLETE)
(V2 Stage A — Signal Census: COMPLETE)

## Phase List

### Phase 0 — Project Constitution
Goal: Produce all project control files that govern every future session.
Status: [x] Complete

Build:
  [x] context.md — product definition, frozen stack, scope, auth, data flow, env vars, deployment, session protocol
  [x] build.md — phase list with checklists, promotion rules, deferred log
  [x] diff.md — format reference and first session entry
  [x] decisions.md — format reference and seed decisions DR-1 through DR-10

Definition of Done:
  [x] context.md has all 8 sections complete
  [x] build.md has all 10 phases (0–9) with status markers
  [x] diff.md has format reference and first entry
  [x] decisions.md has DR-1 through DR-10 with no unresolved DECISION NEEDED
  [x] STACK FROZEN line present in context.md
  [x] Session protocol block present in context.md verbatim
  [x] No application code, route handlers, or configuration files were created

Test stack:
  Manual review of all four control files for completeness and cross-referencing

---

### Phase 1 — Data Contracts + Schemas
Goal: Define all Pydantic schema models and golden JSON fixtures so every future phase speaks the same language.
Status: [x] Complete

Build:
  [x] Project directory scaffold (src layout, packages, tests)
  [x] pyproject.toml with all confirmed dependencies pinned
  [x] .env.example with all env vars from context.md Section 1.6
  [x] .gitignore
  [x] VideoIngestedEvent schema (Pydantic model)
  [x] RouterDecision schema (Pydantic model)
  [x] ExtractorResult schema (Pydantic model, covers ASR and OCR)
  [x] AlignedSegment schema (Pydantic model)
  [x] FinalOutput schema (Pydantic model, all content types)
  [x] AuthToken schema (Pydantic model)
  [x] JWTPayload schema (Pydantic model)
  [x] Golden JSON fixture file for each schema above
  [x] pytest schema validation tests (each fixture validates against its schema without error)

Definition of Done:
  [x] Every core payload has a Pydantic v2 schema
  [x] Every schema has a corresponding golden JSON fixture
  [x] pytest runs and all schema validation tests pass
  [x] No extractor, router, or output model has undocumented fields
  [x] Auth payload shapes are defined (auth is not built yet, only the schema exists)
  [x] ruff check passes on all files in this phase
  [x] mypy passes on all files in this phase

Test stack:
  pytest
  schema validation tests (Pydantic model_validate against fixture)
  ruff check
  mypy

---

### Phase 2 — Ingestion + Temporary Storage
Goal: Accept a YouTube URL and turn it into a temporary, processable asset on local storage.
Status: [x] Complete

Build:
  [x] URL ingestion Celery task (yt-dlp download to TEMP_MEDIA_PATH)
  [x] Video metadata extraction (title, duration, channel, thumbnail)
  [x] Ingestion job record written to PostgreSQL
  [x] VideoIngestedEvent emitted on success (Phase 1 contract)
  [x] Automatic temp file deletion after processing completes
  [x] Retry logic for transient download failures
  [x] Error handling for private/unavailable videos

Definition of Done:
  [x] Valid YouTube URL becomes a temp file in TEMP_MEDIA_PATH
  [x] Duration, codecs, and metadata are stored in the database
  [x] VideoIngestedEvent conforms to Phase 1 schema
  [x] Temp file is automatically removed after processing
  [x] Failed ingest leaves no orphaned media on disk
  [x] Retry handles transient network failures

Test stack:
  pytest
  yt-dlp smoke test (mocked)
  storage integration tests
  retry and failure tests
  temp file lifecycle test

Bugs found and fixed:
  - Bug fixed post-phase: Celery task registration — ytclfr.tasks.ingest not imported during worker startup, fixed by adding import ytclfr.tasks.ingest # noqa: F401, E402 to celery_app.py (Session 7)

---

### Phase 3 — Authentication Layer
Goal: Protect every user-facing endpoint before any output is exposed.
Status: [x] Complete

Build:
  [x] JWT token creation utility
  [x] JWT validation FastAPI dependency
  [x] Auth applied by default to all protected routes
  [x] 401 and 403 response shapes matching Phase 1 contracts
  [x] Rate limiting tied to authenticated identity
  [x] JWT env vars wired from context.md

Definition of Done:
  [x] Unauthenticated request to any protected endpoint returns 401
  [x] Invalid token returns 401
  [x] Valid token passes through
  [x] Rate limit returns 429 after configured threshold
  [x] No credentials hardcoded anywhere

Test stack:
  pytest
  401 on missing token
  401 on invalid token
  200 on valid token
  429 on rate limit breach

---

### Phase 4 — Preflight Router
Goal: Classify the video cheaply before committing to heavy work.
Status: [x] Complete

Build:
  [x] Frame sampler (configurable sample count, not hardcoded)
  [x] Basic audio presence / VAD check
  [x] Title and description metadata inspection
  [x] Content type classifier: speech-heavy, music-heavy, list-edit, slide-presentation, mixed
  [x] RouterDecision output matching Phase 1 schema
  [x] Confidence score attached to every decision
  [x] Low-confidence path explicitly allowed, not rejected

Definition of Done:
  [x] Router returns exactly one primary route per video
  [x] Confidence score is always present
  [x] RouterDecision conforms to Phase 1 contract
  [x] Router has no dependency on Phase 5 extractors

Test stack:
  labeled sample set (min 5 examples per route type)
  routing accuracy tests
  confidence threshold boundary tests
  misroute regression tests

---

### Phase 5 — Worker Queue + Parallel Extractor Infrastructure
Goal: Build the Celery worker foundation and all heavy extractor tasks before any single extractor is wired up.
Status: [x] Complete

Build:
  [x] Celery app configuration (queues: fast, heavy)
  [x] Worker process entry point
  [x] Task base class (retry policy, timeout, error handling)
  [x] Dead-letter handling for tasks that exhaust retries
  [x] Task result storage in Redis
  [x] Worker metrics: duration, failure rate, queue depth
  [x] ASR extractor task (faster-whisper, word-level timestamps)
  [x] OCR extractor task (Tesseract, frame-level timestamps)
  [x] Audio classifier task (speech vs music)
  [x] Orchestration: Celery group (parallel ASR + OCR)
  [x] Chord callback: temporal alignment triggered after group
  [x] ExtractorResult output matching Phase 1 schema

Definition of Done:
  [x] ASR and OCR run in parallel via Celery group
  [x] Each extractor result is timestamped and conforms to ExtractorResult schema
  [x] A failing extractor does not cancel other extractors
  [x] Dead-letter queue receives tasks that exhaust retries
  [x] Worker starts with a single command from project root
  [x] No extractor imports or calls another extractor

Test stack:
  pytest: per-extractor unit tests (mocked models)
  pytest: parallel execution test
  pytest: dead-letter routing test
  integration test on 3 short video clips

Post-phase hardening fixes applied (Session 14):
  - DB session generator leak (FIX 01, FIX 02)
  - Celery worker logging observability (FIX 03)
  - Chord zombie job state (FIX 04)
  - Silent error persistence failure (FIX 05)
  - Inline import locations (FIX 06)
  - O(N) ffmpeg subprocess loop (FIX 07)
  - Deprecated FastAPI on_event (FIX 08)

---

### Phase 6 — Temporal Alignment Layer
Goal: Combine transcript, OCR, and audio outputs into one shared timeline.
Status: [x] Complete

Build:
  [x] Timestamp normalization (common time unit)
  [x] Overlap detection and resolution
  [x] Duplicate evidence merge logic
  [x] Segment creation from aligned evidence
  [x] AlignedSegment output matching Phase 1 schema

Definition of Done:
  [x] One shared timeline exists per video
  [x] Overlaps resolved deterministically
  [x] Duplicate evidence collapsed
  [x] Same input always produces identical output (reproducible)
  [x] AlignedSegment conforms to Phase 1 schema

Test stack:
  pytest: interval merge tests
  pytest: alignment tests
  pytest: reproducibility test (3 runs, identical output)
  property-based tests for overlap edge cases

---

### Phase 7 — Confidence Controller
Goal: Decide whether to trust, rescan, or downgrade results.
Status: [x] Complete

Build:
  [x] Confidence scoring rules per signal type
  [x] Branch switching logic
  [x] Fallback trigger conditions
  [x] Rescanning policy (max attempt limit, not infinite)
  [x] Partial/uncertain output policy (uncertain is valid, not an error)

Definition of Done:
  [x] Low-confidence transcript does not terminate pipeline
  [x] Low-confidence OCR triggers additional frame sampling
  [x] Uncertain output is explicitly marked, never silently dropped
  [x] Rescan stops at max attempt limit
  [x] Confidence Controller has no DB writes, no queue calls

Test stack:
  pytest: scoring rule unit tests
  pytest: failure injection per signal type
  pytest: rescan max limit enforcement
  property-based: confidence score always in [0.0, 1.0]

---

### Phase 8 — Storage + Output API
Goal: Persist structured knowledge to Postgres and expose it to authenticated users.
Status: [x] Complete

Build:
  [x] PostgreSQL schema (aligned_timelines table via Alembic migration)
  [x] pgvector integration for semantic retrieval on AlignedSegment embeddings
  [x] PostgreSQL GIN index for fast keyword search on timeline text
  [x] FastAPI output layer with Phase 3 auth on all routes
  [x] Redis cache for repeated identical queries
  [x] FinalOutput JSON response matching Phase 1 contract (including provenance/confidence)
  [x] Query endpoints: by job_id, by time range, by semantic similarity (pgvector)
  [x] tasks/align.py updated to persist final timeline to DB

Definition of Done:
  [x] Results queryable by job_id and time range
  [x] Output conforms to Phase 1 FinalOutput schema
  [x] Repeated requests served from Redis cache
  [x] All routes protected by Phase 3 auth
  [x] Alembic migration runs clean from zero
  [x] No Base.metadata.create_all() anywhere in codebase
  [x] Zero references to OpenSearch/Elasticsearch

Test stack:
  Alembic migration tests (upgrade and downgrade)
  pgvector search tests
  API contract tests against FinalOutput schema
  cache hit/miss tests
  load tests at 2x expected peak

---

### Phase 9 — End-to-End Hardening
Goal: Make the system production-safe, observable, and recoverable.
Status: In Progress

Build:
  [ ] Distributed tracing (trace ID in all logs and responses)
  [ ] Metrics: latency, cost per video, failure rate, queue depth
  [ ] Dead-letter handling and alerting
  [ ] Idempotency on all task retries
  [ ] Partial-result recovery (resume from last successful phase)
  [ ] Security audit (OWASP API Top 10 check)
  [ ] bandit static analysis (zero high-severity findings)
  [ ] Load and chaos testing
  [ ] Runbook for every failure mode found in chaos testing

Definition of Done:
  [ ] Pipeline survives failure of any single phase without data corruption
  [ ] Reruns of any job are safe and idempotent
  [ ] bandit produces zero high-severity findings
  [ ] Every chaos test failure has a runbook entry
  [ ] Trace ID present in every log line and API response header

Test stack:
  full end-to-end tests on 5 real video URLs
  chaos tests: kill worker mid-task, kill DB mid-write
  recovery tests: resume from checkpoint per phase
  load tests: sustained 2x peak for 10 minutes
  cost profiling: cost per video within acceptable range

---

### Phase 10 — V2 Distributed Scaling
Goal: Eliminate local filesystem coupling between Celery workers and enable distributed multi-node deployment via S3 object storage and lightweight chord payloads.
Status: [x] Complete

Build:
  [x] AWS S3 settings added to Settings class (config.py)
  [x] S3StorageManager created (ingestion/s3_storage.py)
  [x] Alembic migration 0004: s3_video_uri column on jobs table
  [x] Ingestion task uploads video to S3, cleans local copy immediately
  [x] Router and extract tasks download video from S3 before processing
  [x] Chord payloads reduced to lightweight dicts (no JSON in Redis)
  [x] build_timeline fetches extractor results from Postgres instead of chord args
  [x] Proxy-aware rate limiting (X-Forwarded-For)
  [x] boto3 added to pyproject.toml dependencies
  [x] DR-18, DR-19, DR-20 written to decisions.md
  [x] diff.md updated

Definition of Done:
  [x] No local filesystem path is shared between Celery workers
  [x] Video files transit through S3 between ingestion and extraction
  [x] Chord callback receives only lightweight status dicts, not full JSON payloads
  [x] Alignment engine reads extractor data from Postgres, not from Redis chord args
  [x] Rate limiter uses real client IP behind load balancer
  [x] All existing Phase 6 and Phase 7 tests still pass
  [x] ruff check passes
  [x] mypy passes

Test stack:
  ruff check
  mypy
  pytest (existing alignment, confidence, extractor tests must not break)

---

### V2 Stage A — Signal Census
Goal: Replace the V1 preflight router with a lightweight probing layer that detects what signals physically exist in the video before any expensive extraction runs.
Status: [x] Complete

Build:
  [x] A-1: Define `SignalManifest` Pydantic model (`contracts/manifest.py`)
  [x] A-2: Add `signal_manifests` Alembic migration (`migrations/`)
  [x] A-3: Add `SignalManifestRepository` to storage layer (`storage/manifest_store.py`)
  [x] A-4: Upgrade `audio_checker.py` — VAD + music detection (`probing/audio_checker.py`)
  [x] A-5: Upgrade `frame_sampler.py` — motion + face + text density (`probing/frame_sampler.py`)
  [x] A-6: Add `metadata_probe.py` — yt-dlp metadata parser (`probing/metadata_probe.py`)
  [x] A-7: Write `tasks/stage_a.py` Celery task (orchestrates A-4/A-5/A-6, saves manifest) (`tasks/stage_a.py`)
  [x] A-8: Add SSE event types for Stage A (`contracts/events.py`)
  [x] A-9: Golden JSON fixture + unit tests for SignalManifest (`tests/fixtures/signal_manifest.json`, `tests/test_stage_a.py`)

Definition of Done:
  [x] All Stage A micro-tasks complete.
  [x] 27 unit tests for Stage A pass without error.
  [x] V1 regression tests pass with no regressions.
  [x] All intermediate results (SignalManifest) persisted to PostgreSQL.
  [x] SSE events emitted at every step of Stage A.

Test stack:
  pytest tests/unit/stage_a/
  pytest tests/ -q

---

### V2 Stage B — Targeted Extraction
Goal: Read the `SignalManifest` and dynamically build a Celery group of only the extractors needed. No extractor runs unless its signal was confirmed in Stage A.
Status: [ ] In Progress

Build:
  [ ] B-1: Define extractor output Pydantic models (`ASROutput`, `OCROutput`, `VisualOutput`) (`contracts/extractor_outputs.py`)
  [ ] B-2: Add extractor output tables (Alembic migration) (`migrations/`)
  [ ] B-3: Refactor `tasks/asr.py` to V2 contract (`tasks/asr.py`)
  [ ] B-4: Refactor `tasks/ocr.py` to V2 contract (`tasks/ocr.py`)
  [ ] B-5: Add `tasks/visual_extractor.py` (scene cut + face detection) (`tasks/visual_extractor.py`)
  [ ] B-6: Write `tasks/stage_b.py` — reads manifest, builds dynamic Celery group (`tasks/stage_b.py`)
  [ ] B-7: Add SSE event types for Stage B (`contracts/events.py`)
  [ ] B-8: Golden JSON fixtures + unit tests for Stage B (`tests/fixtures/`, `tests/test_stage_b.py`)

Definition of Done:
  [ ] Extractors only run if the corresponding signal is active in the manifest.
  [ ] Extractor results are persisted as separate records linked to the job in the DB.
  [ ] Tasks are highly robust and run in parallel via Celery groups.
  [ ] SSE events emitted correctly.

Test stack:
  pytest tests/

---

### V2 Stage C — Evidence Fusion
Goal: Take all extractor outputs and produce a single fused evidence graph with aligned timestamps, extracted entities, and confidence scores. LLM call via Groq to answer "what is this video about?"
Status: [ ] Planned

Build:
  [ ] C-1: Define `EvidenceGraph`, `FusedSegment`, `ExtractedEntity` Pydantic models (`contracts/evidence.py`)
  [ ] C-2: Add `evidence_graphs` Alembic migration (`migrations/`)
  [ ] C-3: Upgrade `alignment/engine.py` to V2 temporal alignment (`alignment/engine.py`)
  [ ] C-4: Write `fusion/entity_extractor.py` (extracts products, people, places from transcript) (`fusion/entity_extractor.py`)
  [ ] C-5: Write `fusion/groq_reasoner.py` (Groq API call: dominant subject + scene summary) (`fusion/groq_reasoner.py`)
  [ ] C-6: Write `tasks/stage_c.py` — fuses all evidence, saves EvidenceGraph (`tasks/stage_c.py`)
  [ ] C-7: Add SSE event types for Stage C (`contracts/events.py`)
  [ ] C-8: Golden JSON fixtures + unit tests for Stage C (`tests/fixtures/`, `tests/test_stage_c.py`)

---

### V2 Stage D — Taxonomy + Intent Mapping
Goal: Use the `EvidenceGraph` to produce a final structured classification: parent category, child category, intent. This is the last step — classification happens only after evidence is complete.
Status: [ ] Planned

Build:
  [ ] D-1: Define enriched `FinalOutput` Pydantic model (`contracts/output.py`)
  [ ] D-2: Update `final_outputs` table (Alembic migration) (`migrations/`)
  [ ] D-3: Write `taxonomy/mapper.py` — Groq-powered taxonomy classification (`taxonomy/mapper.py`)
  [ ] D-4: Write `taxonomy/intent_resolver.py` — resolves intent from evidence (`taxonomy/intent_resolver.py`)
  [ ] D-5: Write `tasks/stage_d.py` — runs mapper, saves FinalOutput (`tasks/stage_d.py`)
  [ ] D-6: Update `storage/output_store.py` to V2 schema (remove hardcoded `content_type_map`) (`storage/output_store.py`)
  [ ] D-7: Add SSE event types for Stage D + job completion (`contracts/events.py`)
  [ ] D-8: Golden JSON fixtures + unit tests for Stage D (`tests/fixtures/`, `tests/test_stage_d.py`)

---

### V2 Pipeline Wiring
Goal: Wire the four independent stages together using Celery callback mechanisms and update job state machines.
Status: [ ] Planned

Build:
  [ ] W-1: Update `tasks/route.py` to trigger Stage A instead of old group (`tasks/route.py`)
  [ ] W-2: Wire Stage A completion → Stage B trigger via Celery callback (`tasks/stage_a.py`)
  [ ] W-3: Wire Stage B completion → Stage C trigger (`tasks/stage_b.py`)
  [ ] W-4: Wire Stage C completion → Stage D trigger (`tasks/stage_c.py`)
  [ ] W-5: Update job status state machine in DB (`storage/job_store.py`)
  [ ] W-6: Update FastAPI job status endpoint to return new fields (`api/jobs.py`)
  [ ] W-7: Integration test: full pipeline on a short test video (`tests/test_pipeline_integration.py`)

---

## Phase Promotion Rules

A phase may only be marked complete when:
- Every Build item has a checkmark
- Every Definition of Done item is verifiably true
- Every test in the test stack is passing
- diff.md has been updated for the closing session
- The Current Phase Marker has been updated to the next phase

No phase may be skipped. No item may be removed from a phase checklist without a SCOPE REVIEW entry in diff.md.

## Deferred Items Log

(empty — no items deferred yet)
