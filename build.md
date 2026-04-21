# build.md

CURRENT PHASE: 4 — Preflight Router
STATUS: IN PROGRESS
(Phase 0 — Project Constitution: COMPLETE)
(Phase 1 — Data Contracts + Schemas: COMPLETE)
(Phase 2 — Ingestion + Temporary Storage: COMPLETE)
(Phase 3 — Authentication Layer: COMPLETE)

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
  [ ] JWT token creation utility
  [ ] JWT validation FastAPI dependency
  [ ] Auth applied by default to all protected routes
  [ ] 401 and 403 response shapes matching Phase 1 contracts
  [ ] Rate limiting tied to authenticated identity
  [ ] JWT env vars wired from context.md

Definition of Done:
  [ ] Unauthenticated request to any protected endpoint returns 401
  [ ] Invalid token returns 401
  [ ] Valid token passes through
  [ ] Rate limit returns 429 after configured threshold
  [ ] No credentials hardcoded anywhere

Test stack:
  pytest
  401 on missing token
  401 on invalid token
  200 on valid token
  429 on rate limit breach

---

### Phase 4 — Preflight Router
Goal: Classify the video cheaply before committing to heavy work.
Status: [ ] In Progress

Build:
  [ ] Frame sampler (configurable sample count, not hardcoded)
  [ ] Basic audio presence / VAD check
  [ ] Title and description metadata inspection
  [ ] Content type classifier: speech-heavy, music-heavy, list-edit, slide-presentation, mixed
  [ ] RouterDecision output matching Phase 1 schema
  [ ] Confidence score attached to every decision
  [ ] Low-confidence path explicitly allowed, not rejected

Definition of Done:
  [ ] Router returns exactly one primary route per video
  [ ] Confidence score is always present
  [ ] RouterDecision conforms to Phase 1 contract
  [ ] Router has no dependency on Phase 5 extractors

Test stack:
  labeled sample set (min 5 examples per route type)
  routing accuracy tests
  confidence threshold boundary tests
  misroute regression tests

---

### Phase 5 — Worker Queue + Parallel Extractor Infrastructure
Goal: Build the Celery worker foundation and all heavy extractor tasks before any single extractor is wired up.
Status: [ ] Not Started

Build:
  [ ] Celery app configuration (queues: fast, heavy)
  [ ] Worker process entry point
  [ ] Task base class (retry policy, timeout, error handling)
  [ ] Dead-letter handling for tasks that exhaust retries
  [ ] Task result storage in Redis
  [ ] Worker metrics: duration, failure rate, queue depth
  [ ] ASR extractor task (faster-whisper, word-level timestamps)
  [ ] OCR extractor task (Tesseract, frame-level timestamps)
  [ ] Audio classifier task (speech vs music)
  [ ] Orchestration: Celery group (parallel ASR + OCR)
  [ ] Chord callback: temporal alignment triggered after group
  [ ] ExtractorResult output matching Phase 1 schema

Definition of Done:
  [ ] ASR and OCR run in parallel via Celery group
  [ ] Each extractor result is timestamped and conforms to ExtractorResult schema
  [ ] A failing extractor does not cancel other extractors
  [ ] Dead-letter queue receives tasks that exhaust retries
  [ ] Worker starts with a single command from project root
  [ ] No extractor imports or calls another extractor

Test stack:
  pytest: per-extractor unit tests (mocked models)
  pytest: parallel execution test
  pytest: dead-letter routing test
  integration test on 3 short video clips

---

### Phase 6 — Temporal Alignment Layer
Goal: Combine transcript, OCR, and audio outputs into one shared timeline.
Status: [ ] Not Started

Build:
  [ ] Timestamp normalization (common time unit)
  [ ] Overlap detection and resolution
  [ ] Duplicate evidence merge logic
  [ ] Segment creation from aligned evidence
  [ ] AlignedSegment output matching Phase 1 schema

Definition of Done:
  [ ] One shared timeline exists per video
  [ ] Overlaps resolved deterministically
  [ ] Duplicate evidence collapsed
  [ ] Same input always produces identical output (reproducible)
  [ ] AlignedSegment conforms to Phase 1 schema

Test stack:
  pytest: interval merge tests
  pytest: alignment tests
  pytest: reproducibility test (3 runs, identical output)
  property-based tests for overlap edge cases

---

### Phase 7 — Confidence Controller
Goal: Decide whether to trust, rescan, or downgrade results.
Status: [ ] Not Started

Build:
  [ ] Confidence scoring rules per signal type
  [ ] Branch switching logic
  [ ] Fallback trigger conditions
  [ ] Rescanning policy (max attempt limit, not infinite)
  [ ] Partial/uncertain output policy (uncertain is valid, not an error)

Definition of Done:
  [ ] Low-confidence transcript does not terminate pipeline
  [ ] Low-confidence OCR triggers additional frame sampling
  [ ] Uncertain output is explicitly marked, never silently dropped
  [ ] Rescan stops at max attempt limit
  [ ] Confidence Controller has no DB writes, no queue calls

Test stack:
  pytest: scoring rule unit tests
  pytest: failure injection per signal type
  pytest: rescan max limit enforcement
  property-based: confidence score always in [0.0, 1.0]

---

### Phase 8 — Storage + Output API
Goal: Persist structured knowledge and expose it to authenticated users.
Status: [ ] Not Started

Build:
  [ ] PostgreSQL schema (jobs, metadata, results via Alembic)
  [ ] pgvector for semantic retrieval on AlignedSegment embeddings
  [ ] FastAPI output layer with Phase 3 auth on all routes
  [ ] Redis cache for repeated identical queries
  [ ] FinalOutput JSON response matching Phase 1 schema
  [ ] Query endpoints: by job_id, by time range, by similarity
  [ ] GET /api/v1/jobs/{job_id}/result endpoint

Definition of Done:
  [ ] Results queryable by job_id and by time range
  [ ] Output conforms to Phase 1 FinalOutput schema
  [ ] Repeated requests served from Redis cache
  [ ] All routes protected by Phase 3 auth
  [ ] Alembic migration runs clean from zero
  [ ] No Base.metadata.create_all() anywhere in codebase

Test stack:
  Alembic migration tests (upgrade and downgrade)
  pgvector search tests
  API contract tests against FinalOutput schema
  cache hit/miss tests
  load tests at 2x expected peak

---

### Phase 9 — End-to-End Hardening
Goal: Make the system production-safe, observable, and recoverable.
Status: [ ] Not Started

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
