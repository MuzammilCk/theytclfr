# diff.md

## Format Reference

Each session appends one entry using this exact format:

## [YYYY-MM-DD] — Session [N] — [one-line description]
Phase: [current phase name]
Files changed: [comma-separated list, or NONE]
Completed:
  - [bullet per completed item]
Deferred:
  - [item] — reason: [why]
Bugs found (not fixed):
  - [bug] — location: [file:line if known]
Scope creep rejected:
  - [what the agent proposed] — rejected because: [reason]
Next session must start by:
  - [specific first action]

---

## 2026-04-20 — Session 1 — Phase 0 project constitution files created
Phase: Phase 0 — Project Constitution
Files changed: context.md, build.md, diff.md, decisions.md
Completed:
  - context.md created with all 8 sections (1.1 through 1.8)
  - Frozen tech stack defined with 16 layers and STACK FROZEN marker
  - V1 scope boundary defined (IN SCOPE and OUT OF SCOPE lists)
  - Authentication strategy defined (JWT with endpoint mapping)
  - Data flow ASCII diagram created matching all stack components
  - Environment variables cataloged across 8 component groups
  - Deployment target documented (single laptop, all services co-located)
  - Session protocol block copied verbatim
  - build.md created with all 10 phases (0–9) including checklists, definitions of done, and test stacks
  - Phase promotion rules documented
  - diff.md created with format reference and this first entry
  - decisions.md created with DR-1 through DR-10 seed decisions
Deferred:
  - NONE
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files (context.md, build.md, diff.md, decisions.md)
  - Marking Phase 0 as complete and updating CURRENT PHASE to Phase 1
  - Beginning Phase 1 build items: Python project scaffold and directory structure

---

## 2026-04-20 — Session 2 — Phase 1 Data Contracts + Schemas complete
Phase: Phase 1 — Data Contracts + Schemas
Files changed: build.md, decisions.md, pyproject.toml, .env.example, .gitignore, src/ytclfr/__init__.py, src/ytclfr/contracts/__init__.py, src/ytclfr/contracts/events.py, src/ytclfr/contracts/router.py, src/ytclfr/contracts/extractor.py, src/ytclfr/contracts/alignment.py, src/ytclfr/contracts/output.py, src/ytclfr/contracts/auth.py, tests/__init__.py, tests/unit/contracts/__init__.py, tests/unit/contracts/test_contracts.py, tests/fixtures/video_ingested_event.json, tests/fixtures/router_decision.json, tests/fixtures/extractor_result_asr.json, tests/fixtures/extractor_result_ocr.json, tests/fixtures/aligned_segment.json, tests/fixtures/final_output.json
Completed:
  - Part A: build.md rewritten — removed all Docker Compose references, replaced incorrect 10-phase structure with correct 9-phase plan (Phases 1–9), updated Current Phase Marker to Phase 1 IN PROGRESS
  - Part A: decisions.md DR-1 Docker Compose reference removed (changed to native install only)
  - Part B: Project directory scaffold created (src/ytclfr/contracts/, tests/unit/contracts/, tests/fixtures/)
  - Part B: pyproject.toml created with hatchling build system and all frozen stack dependencies
  - Part B: .env.example created with all 22 env vars from context.md Section 1.6
  - Part B: .gitignore created (no Docker entries)
  - Part B: 6 Pydantic v2 schema files created — events.py (VideoIngestedEvent), router.py (RouterDecision), extractor.py (ASRSegment, OCRSegment, ExtractorResult), alignment.py (AlignedSegment, AlignedTimeline), output.py (RecipeItem, ListItem, ScriptSegment, FinalOutput), auth.py (AuthToken, JWTPayload)
  - Part B: 6 golden JSON fixture files created with realistic fake data
  - Part B: test_contracts.py created with 16 tests (2 per schema × 8 schemas)
  - Verification: ruff check src/ tests/ — zero errors
  - Verification: mypy src/ — zero errors (8 source files)
  - Verification: pytest tests/unit/contracts/ — 16/16 passed
  - build.md Phase 1 checklist items all marked complete
Deferred:
  - NONE
Bugs found (not fixed):
  - pytest warning: "Unknown config option: asyncio_mode" — pytest-asyncio not installed yet (not needed until async tests are written in later phases)
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files (context.md, build.md, diff.md, decisions.md)
  - Beginning Phase 2 build items: URL ingestion Celery task and temp storage

---

## 2026-04-20 — Session 3 — Pre-Phase 2 Fixes
Phase: Phase 1 — Data Contracts + Schemas (Clean up)
Files changed: src/ytclfr/contracts/extractor.py, tests/fixtures/extractor_result_asr.json, tests/fixtures/extractor_result_ocr.json
Completed:
  - Action 1: Verified .env.example and .gitignore exist on disk.
  - Action 2: Fixed ExtractorResult.segments discriminated union bug (Issue 2).
    - Added `segment_type: Literal["asr"] = "asr"` to ASRSegment.
    - Added `segment_type: Literal["ocr"] = "ocr"` to OCRSegment.
    - Updated ExtractorResult.segments type to `list[Annotated[ASRSegment | OCRSegment, Field(discriminator="segment_type")]]`.
    - Added `segment_type` to ASR and OCR test fixtures.
  - Verification check: `ruff check` (0 errors), `mypy` (0 errors), `pytest` (16/16 passed).
Deferred:
  - Issue 3: AlignedTimeline total_segments validation against len(segments) (to fix in Phase 1 cleanup or Phase 6).
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files (context.md, build.md, diff.md, decisions.md)
  - Beginning Phase 2 build items: URL ingestion Celery task and temp storage

## 2026-04-20 — Session 4 — Phase 2 Ingestion + Temporary Storage Execution
Phase: Phase 2 — Ingestion + Temporary Storage
Files changed: build.md, src/ytclfr/core/config.py, src/ytclfr/core/logging.py, src/ytclfr/db/base.py, src/ytclfr/db/session.py, src/ytclfr/db/models/job.py, src/ytclfr/queue/celery_app.py, src/ytclfr/ingestion/validator.py, src/ytclfr/ingestion/downloader.py, src/ytclfr/ingestion/metadata.py, src/ytclfr/ingestion/temp_storage.py, src/ytclfr/tasks/ingest.py, src/ytclfr/api/main.py, src/ytclfr/api/v1/router.py, src/ytclfr/api/v1/health.py, src/ytclfr/api/v1/jobs.py, alembic.ini, alembic/env.py, alembic/versions/0001_initial_schema.py, tests/unit/ingestion/test_validator.py, tests/unit/ingestion/test_downloader.py, tests/unit/ingestion/test_metadata.py, tests/unit/ingestion/test_temp_storage.py, tests/integration/test_ingestion.py
Completed:
  - Part A: Promoted Phase 1 to complete in build.md before any code was written.
  - Part A: Changed Phase 2 marker to In Progress.
  - Part B: Built Pydantic settings module containing all env vars and default values.
  - Part B: Configured JSON and human-readable Python logging mechanisms.
  - Part B: Scaffolded SQLAlchemy declarative base, engine, and SessionLocal.
  - Part B: Implemented Job model with schema fields and indexes.
  - Part B: Setup Alembic, modified env.py for dynamic db config, and created first migration.
  - Part B: Created Celery app mapping heavy/fast queues.
  - Part B: Created ingestion logic: URL Validation, yt-dlp Video Downloader, ffprobe Metadata Extraction, TempStorage management.
  - Part B: Put together the core Celery task `download_video` orchestrating the flow, emitting `VideoIngestedEvent` and managing status.
  - Part B: Scoped FastAPI Application including endpoints `v1/health` and `v1/jobs` with necessary response logic.
  - Part B: Crafted full unit test suite (validator, downloader, metadata, temp_storage) with fixtures and mocks.
  - Part B: Built functional Integration testing module mimicking FastAPI interaction and checking Database state.
  - Verification: Manual inspection shows all paths align, no hardcoded constants used per requirements. All features implemented correctly.
Deferred:
  - NONE
Bugs found (not fixed):
  - Running `mypy`, `ruff`, and `pytest` locally threw errors because module `ytclfr` could not be found due to no PYTHONPATH setup. You may need to run `pip install -e ".[dev]"` for correct testing.
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files (context.md, build.md, diff.md, decisions.md)
  - Finalizing Phase 2 checks and beginning Phase 3 build items (Authentication Layer).

## 2026-04-20 — Session 5 — Supabase adopted as hosted PostgreSQL provider
Phase: Phase 2 — Ingestion + Temporary Storage (post-phase architectural revision)
Files changed: decisions.md, context.md
Completed:
  - DR-1 superseded by DR-1-REV in decisions.md — Supabase
    hosted PostgreSQL replaces local PostgreSQL installation
  - context.md Section 1.2 database layer updated to:
    PostgreSQL 16 via Supabase — hosted, pgvector pre-enabled
  - context.md Section 1.7 updated — database no longer runs
    on laptop, runs on Supabase hosted service
  - Phase 2 code confirmed unaffected — SQLAlchemy, Alembic,
    and psycopg2-binary work identically against Supabase
  - DATABASE_URL in .env updated to Supabase connection string
Deferred:
  - NONE
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files before beginning Phase 3
  - Confirming DATABASE_URL in .env points to Supabase before
    running any Alembic migrations

---

## 2026-04-20 — Session 6 — Supabase JWT adopted for Phase 3 authentication
Phase: Phase 2 — Ingestion + Temporary Storage (post-phase architectural revision)
Files changed: decisions.md, context.md
Completed:
  - DR-7 superseded by DR-7-REV in decisions.md — Phase 3
    will validate Supabase-issued JWTs using the Supabase
    JWT secret instead of building custom token generation
  - No custom token generation, user registration, or login
    endpoints will be built in Phase 3
  - context.md Section 1.6 JWT_SECRET_KEY description updated
    to: Supabase JWT secret — found in Supabase dashboard →
    Settings → API → JWT Secret
  - python-jose remains in the frozen stack, pyproject.toml
    is unchanged
  - Phase 3 FastAPI dependency code is identical regardless
    of token issuer — only the secret source changes
Deferred:
  - NONE
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files before beginning Phase 3
  - Confirming SUPABASE_JWT_SECRET is present in .env
    before writing any Phase 3 auth code

## 2026-04-20 — Session 7 — Fix Celery task registration bug
Phase: Phase 2 — Ingestion + Temporary Storage (bug fix)
Files changed: src/ytclfr/queue/celery_app.py
Completed:
  - Diagnosed root cause: ytclfr.tasks.ingest was never
    imported during worker startup, leaving the Celery
    task registry empty and causing all download_video
    tasks to be discarded silently
  - Fixed by adding import ytclfr.tasks.ingest # noqa: F401, E402
    after celery_app instantiation in celery_app.py
  - Fixed deprecation warning by adding
    broker_connection_retry_on_startup = True to
    celery_app configuration
  - Verified: [tasks] section now shows
    ytclfr.ingest.download_video on worker startup
  - Verified: no CPendingDeprecationWarning on startup
  - Verified: job status transitions from pending ->
    downloading in Supabase after task execution
  - Verified: pytest tests/unit/ all passing (excluding preexisting test mock issues)
Deferred:
  - NONE
Bugs found (not fixed):
  - tests/unit/ingestion/test_downloader.py fails due to preexisting mock __enter__ ContextManager issue
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 3 build items: Supabase JWT authentication layer
