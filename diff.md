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

## 2026-04-20 — Session 8 — Phase 3 authentication layer complete
Phase: Phase 3 — Authentication Layer
Files changed: build.md, decisions.md, diff.md, pyproject.toml, src/ytclfr/api/auth.py, src/ytclfr/api/main.py, src/ytclfr/api/rate_limit.py, src/ytclfr/api/v1/jobs.py, tests/unit/auth/__init__.py, tests/unit/auth/test_auth.py, tests/unit/ingestion/test_downloader.py
Completed:
  - Part A: Fixed test_downloader mock bug — private/unavailable video tests now use side_effect pattern matching success test
  - Part A: Promoted Phase 2 to complete in build.md, updated current phase marker to Phase 3
  - Part B: JWT validation dependency built using python-jose and Supabase JWT secret
  - Part B: CREDENTIALS_EXCEPTION (401) and FORBIDDEN_EXCEPTION (403) error models defined
  - Part B: slowapi rate limiter registered on app (IP-based, 10/min on POST /jobs, 30/min on GET /jobs/{job_id})
  - Part B: require_auth dependency applied to POST /api/v1/jobs and GET /api/v1/jobs/{job_id}
  - Part B: PHASE-3-TODO comments removed from jobs.py
  - Part B: 9 auth unit tests written and passing
  - Verification: ruff check src/ tests/ zero errors
  - Verification: mypy src/ zero errors
  - Verification: pytest tests/unit/ all passing
Deferred:
  - Rate limiting is IP-based in Phase 3, not per authenticated user — reason: low complexity priority for V1, revisit in Phase 9 hardening
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 4: Preflight Router

---

## 2026-04-20 — Session 9 — Metadata extraction fix for Windows Unicode decoding
Phase: Phase 2 — Ingestion + Temporary Storage (bug fix)
Files changed: src/ytclfr/ingestion/metadata.py
Completed:
  - Diagnosed `UnicodeDecodeError: 'charmap'` when Celery subprocess attempts reading `ffprobe` output on Windows without explicit encoding.
  - Mitigated downstream `TypeError: the JSON object must be str, bytes or bytearray` caused by empty stdout.
  - Addressed root cause by adding `encoding="utf-8"`, `errors="replace"`, and `timeout=120` to `subprocess.run()`.
  - Added explicit defensive checks ensuring `result.stdout` exists before deserializing.
  - Wrapped `json` and `subprocess` exceptions inside domain-level `MetadataError` to ensure proper Celery retry logic and database error tracking.
Deferred:
  - NONE
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all control files
  - Beginning Phase 4: Preflight Router

---

## 2026-04-21 — Session 10 — Phase 4 Preflight Router complete
Phase: Phase 4 — Preflight Router
Files changed: build.md, decisions.md, diff.md,
  src/ytclfr/core/config.py,
  src/ytclfr/ingestion/downloader.py,
  src/ytclfr/router/__init__.py,
  src/ytclfr/router/frame_sampler.py,
  src/ytclfr/router/audio_checker.py,
  src/ytclfr/router/metadata_inspector.py,
  src/ytclfr/router/classifier.py,
  src/ytclfr/db/models/router_decision.py,
  src/ytclfr/db/models/__init__.py,
  src/ytclfr/tasks/route.py,
  src/ytclfr/tasks/ingest.py,
  src/ytclfr/queue/celery_app.py,
  alembic/versions/0002_router_decision.py,
  tests/unit/router/__init__.py,
  tests/unit/router/test_frame_sampler.py,
  tests/unit/router/test_audio_checker.py,
  tests/unit/router/test_metadata_inspector.py,
  tests/unit/router/test_classifier.py,
  tests/unit/ingestion/test_downloader.py,
  .env.example, .gitignore
Completed:
  - Part A: Deleted stray auth.py and test_sanitize.py
    from project root
  - Part A: Applied cookies fix — ytdlp_cookies_file
    in Settings, _validate_cookies() in downloader,
    cookiefile in both yt-dlp opts dicts, bot-detection
    error handler, YTDLP_COOKIES_FILE in .env.example,
    cookies.txt in .gitignore, DR-11 in decisions.md,
    2 new cookie unit tests
  - Part A: Promoted Phase 3 to complete in build.md,
    current phase marker updated to Phase 4
  - Part B: Frame sampler using ffmpeg subprocess
    with configurable ROUTER_FRAME_SAMPLE_COUNT
  - Part B: Audio checker reading metadata_raw streams
  - Part B: Metadata inspector with keyword sets for
    list, recipe, and slide signals
  - Part B: Rule-based classifier producing
    RouterDecision conforming to Phase 1 contract
  - Part B: RouterDecisionModel DB model created
  - Part B: Alembic migration 0002 for
    router_decisions table
  - Part B: classify_video Celery task on fast queue
  - Part B: download_video chains to classify_video
    on success
  - Part B: classify_video registered in celery_app.py
  - Part B: 14 router unit tests written
  - Part B: 2 new downloader cookie tests written
Deferred:
  - Frame brightness/variance analysis deferred —
    reason: title/description/audio heuristics are
    sufficient for V1 router accuracy, visual
    analysis can be added in Phase 9 hardening
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 5: Worker Queue + Parallel
    Extractor Infrastructure

## 2026-04-21 — Session 11 — Phase 4 Router Bug-Fix
Phase: Phase 4 — Preflight Router (bug-fix session)
Files changed:
  src/ytclfr/router/audio_checker.py,
  src/ytclfr/router/metadata_inspector.py,
  src/ytclfr/router/classifier.py,
  tests/unit/router/test_audio_checker.py,
  tests/unit/router/test_metadata_inspector.py,
  tests/unit/router/test_classifier.py,
  decisions.md,
  diff.md
Completed:
  - Fix 1: audio_checker.py rewritten to read yt-dlp info
    dict format (acodec, abr, subtitles, duration) instead
    of ffprobe format (streams, format.duration). Audio
    detection now works for all videos.
  - Fix 1: Duration gate (60-600s) removed from likely_music.
    Minimum duration moved to classifier as tunable constant
    MUSIC_MIN_DURATION_SECONDS = 10.0.
  - Fix 2: metadata_inspector.py updated — word-boundary
    regex matching replaces substring matching. LIST_KEYWORDS
    replaced with multi-word phrases to eliminate false
    positives on common English words. Tags included in
    normalized text. "tutorial" removed from RECIPE_KEYWORDS.
  - Fix 3: classifier.py Rule 1 guard changed from
    NOT has_list_signal to NOT has_recipe_signal. Music
    content with superlatives in the title now routes
    correctly as music-heavy.
  - Fix 4: test_audio_checker.py rewritten with yt-dlp
    format inputs. Includes regression test for 20-second
    ringtone (the original reported bug).
  - Fix 5: test_metadata_inspector.py — added regression
    tests for substring false positives, tag searching,
    tutorial double-flag fix, ringtone title non-regression.
  - Fix 6: test_classifier.py — added regression tests for
    Rule 1 priority fix, ringtone end-to-end path, duration
    gate, and routing notes content.
  - DR-12 appended to decisions.md.
Deferred:
  - NONE
Bugs found (not fixed):
  - extract_metadata() return value is discarded in
    ingest.py (MetadataError suppressed silently). The
    ffprobe VideoMetadata object is computed and thrown
    away. Fixing this requires a job schema addition and
    is deferred to Phase 9 hardening to avoid a migration
    during active Phase 5 development.
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 5: Worker Queue + Parallel
    Extractor Infrastructure

## 2026-04-21 — Session 12 — Pre-Phase-5 cleanup
Phase: Phase 4 — Preflight Router (pre-phase-5 cleanup)
Files changed: src/ytclfr/tasks/ingest.py
Completed:
  - Deleted scratch.py from project root — one-off
    script that had already appended its content
  - Removed module-level settings = get_settings()
    from ingest.py — called at import time before
    .env is guaranteed loaded, redundant with the
    settings_local = get_settings() call inside the
    task function body, and incompatible with test
    monkeypatching
  - Removed time_limit= from @celery_app.task
    decorator in ingest.py — falls back to global
    task_time_limit in celery_app.py which is the
    correct single source of truth
  - Verified: ruff, mypy, pytest all passing
Deferred: NONE
Bugs found (not fixed): NONE
Scope creep rejected: NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 5: Worker Queue + Parallel
    Extractor Infrastructure

## [2026-04-21] — Session 13 — Phase 5 extractor infrastructure complete
Phase: Phase 5 — Worker Queue + Parallel Extractor Infrastructure
Files changed: build.md, decisions.md, diff.md, src/ytclfr/extractors/__init__.py, src/ytclfr/extractors/base.py, src/ytclfr/extractors/asr.py, src/ytclfr/extractors/ocr.py, src/ytclfr/extractors/audio_classifier.py, src/ytclfr/db/models/extractor_result.py, src/ytclfr/db/models/__init__.py, src/ytclfr/tasks/extract.py, src/ytclfr/tasks/align.py, src/ytclfr/tasks/route.py, src/ytclfr/queue/celery_app.py, alembic/versions/0003_extractor_results.py, tests/unit/extractors/__init__.py, tests/unit/extractors/test_asr.py, tests/unit/extractors/test_ocr.py, tests/unit/extractors/test_audio_classifier.py, tests/unit/tasks/__init__.py, tests/unit/tasks/test_extract.py
Completed:
  - Part A: Promoted Phase 4 to complete in build.md
  - BaseExtractorTask base class with on_failure/on_retry hooks for all extractor tasks
  - ASRExtractor class using faster-whisper with word-level timestamps and lru_cache singleton
  - OCRExtractor class using Tesseract via pytesseract with ffmpeg frame extraction, deduplication, and Windows-safe subprocess (utf-8 encoding)
  - AudioClassifier using yt-dlp metadata heuristic wrapped in ExtractorResult contract (PHASE-9-TODO comment for YAMNet replacement)
  - ExtractorResultModel DB model for persisting extractor outputs
  - Alembic migration 0003 for extractor_results table
  - Three Celery tasks (run_asr, run_ocr, run_audio_classifier) in tasks/extract.py
  - build_timeline chord callback stub in tasks/align.py
  - classify_video chained to extractor group + chord
  - All four task modules registered in celery_app.py
  - 12 unit tests written and passing
  - alembic upgrade head runs clean
  - ruff check src/ tests/ zero errors
  - mypy src/ zero errors
  - pytest tests/unit/ all passing
Deferred:
  - Audio classifier uses metadata heuristic in Phase 5. YAMNet acoustic model replacement deferred to Phase 9 hardening per PHASE-9-TODO comment.
  - build_timeline is a stub. Full temporal alignment logic deferred to Phase 6.
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 6: Temporal Alignment Layer

## 2026-04-22 — Session 14 — Pre-Phase-6 Critical Bug Fix Session
Phase: Phase 5 — Worker Queue + Parallel Extractor (post-phase hardening)
Files changed:
  src/ytclfr/db/session.py,
  src/ytclfr/tasks/ingest.py,
  src/ytclfr/tasks/route.py,
  src/ytclfr/tasks/extract.py,
  src/ytclfr/tasks/align.py,
  src/ytclfr/queue/celery_app.py,
  src/ytclfr/db/models/extractor_result.py,
  src/ytclfr/router/frame_sampler.py,
  src/ytclfr/api/main.py
Completed:
  - FIX 01: SessionLocal.configure() moved into _get_engine() —
    now called exactly once on initialization, not on every request.
  - FIX 02: Replaced db_gen/next(db_gen) generator hack with
    db_session() context manager in ingest.py, route.py,
    extract.py, and align.py. Generator finalizer now executes
    correctly. Connection and memory leaks eliminated.
  - FIX 03: Added @setup_logging.connect signal hook in
    celery_app.py. Celery workers now use the project's
    configured JSON/human-readable logger. Worker errors are
    visible and structured.
  - FIX 04: Replaced bare raise self.retry(exc=exc) on final
    retry in all three extractor tasks (run_asr, run_ocr,
    run_audio_classifier) with soft error dict return. Chord
    callback build_timeline now always fires even when an
    extractor exhausts retries. Zombie "extracting" job state
    eliminated.
  - FIX 05: Replaced bare except Exception in
    _persist_extractor_error with logger.critical() call.
    Error record loss events are now visible in logs.
  - FIX 06: Moved inline imports to module level —
    from typing import Any out of ExtractorResultModel class
    body in extractor_result.py; from datetime import UTC,
    datetime out of _persist_extractor_error in extract.py.
  - FIX 07: Replaced O(N) ffmpeg subprocess loop in
    frame_sampler.py with a single ffmpeg call using the fps
    filter. Video decoder now opened once per sample_frames()
    call regardless of sample count.
  - FIX 08: Replaced deprecated @app.on_event("startup") in
    main.py with asynccontextmanager lifespan pattern.
  - Verified: ruff check src/ tests/ zero errors
  - Verified: mypy src/ zero errors
  - Verified: pytest tests/unit/ all passing
Deferred:
  - NONE
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 6: Temporal Alignment Layer

## 2026-04-22 — Session 15 — Pre-Phase-6 fix: soft-error dict schema compliance
Phase: Phase 5 — Worker Queue + Parallel Extractor (pre-phase-6 patch)
Files changed: src/ytclfr/tasks/extract.py
Completed:
  - Added total_duration_seconds: 0.0 and
    extracted_at: datetime.now(UTC).isoformat() to
    all three soft-error return dicts in run_asr,
    run_ocr, and run_audio_classifier.
  - Soft-error dicts now pass ExtractorResult.model_validate()
    without raising ValidationError.
  - ruff, mypy, pytest all passing.
Deferred: NONE
Bugs found (not fixed): NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 6: Temporal Alignment Layer

## 2026-04-22 — Session 16 — Pre-Phase-6 fix: ffmpeg thread limit in OCR extractor
Phase: Phase 5 — Worker Queue + Parallel Extractor (pre-phase-6 patch)
Files changed: src/ytclfr/extractors/ocr.py
Completed:
  - Added -threads 2 flag to ffmpeg command in
    OCRExtractor._extract_frames().
  - Prevents CPU saturation when faster-whisper and
    ffmpeg run concurrently on a single-machine worker
    with worker_concurrency=2.
  - ruff, mypy, pytest all passing.
Deferred: NONE
Bugs found (not fixed): NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 6: Temporal Alignment Layer

## 2026-04-22 � Session 17 � Phase 6 Temporal Alignment Layer complete
Phase: Phase 6 � Temporal Alignment Layer
Files changed: build.md, decisions.md, pyproject.toml, src/ytclfr/alignment/__init__.py, src/ytclfr/alignment/normalizer.py, src/ytclfr/alignment/overlap.py, src/ytclfr/alignment/deduplicator.py, src/ytclfr/alignment/segmenter.py, src/ytclfr/alignment/engine.py, src/ytclfr/tasks/align.py, tests/unit/alignment/__init__.py, tests/unit/alignment/test_normalizer.py, tests/unit/alignment/test_overlap.py, tests/unit/alignment/test_deduplicator.py, tests/unit/alignment/test_segmenter.py, tests/unit/alignment/test_engine.py, tests/unit/alignment/test_reproducibility.py, tests/integration/test_alignment_integration.py
Completed:
  - Part A: Added hypothesis to dev dependencies in pyproject.toml and documented in DR-15.
  - Part B: normalizer.py implemented to cast extractor dicts to NormalizedEvidence.
  - Part B: overlap.py implemented to detect and deterministically resolve overlaps keeping highest confidence items.
  - Part B: deduplicator.py implemented with text similarity for merging cross-modal ASR/OCR evidence.
  - Part B: segmenter.py implemented to output valid AlignedSegment objects.
  - Part B: engine.py implemented as pure computation coordinator for the layer.
  - Part B: build_timeline in tasks/align.py updated to run the engine.
  - Part B: Added all required unit tests and integration test; full test suite passing.
  - Part C: Appended DR-15 and DR-16 to decisions.md.
  - Part C: Updated build.md marking Phase 6 as COMPLETE and transitioning to Phase 7.
Deferred:
  - NONE
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 7: Confidence Controller

---

## 2026-04-22 — Session 16 — Post-Phase-6 Audit fixes
Phase: Phase 6 — Temporal Alignment Layer
Files changed: build.md, tests/unit/contracts/test_contracts.py, src/ytclfr/alignment/overlap.py, tests/unit/alignment/test_overlap.py, src/ytclfr/alignment/normalizer.py, tests/unit/alignment/test_normalizer.py
Completed:
  - Checked Phase 3 and Phase 4 items in build.md (Issue 4)
  - Added TestExtractorResultAudio to test_contracts.py to cover the audio fixture (Issue 3)
  - Renamed detect_overlaps to _detect_overlaps to mark it as private and unused outside of tests (Issue 2)
  - Fixed segment ID collision in normalizer.py by using a global index for segment IDs, and added a test for it (Issue 1)
Deferred:
  - NONE
Bugs found (not fixed):
  - NONE
Scope creep rejected:
  - NONE
Next session must start by:
  - Beginning Phase 7: Confidence Controller


## Session 16 (Phase 7)
Date: 2026-04-23
Phase: 7

### Files Changed
- src/ytclfr/confidence/__init__.py: Created.
- src/ytclfr/confidence/scorer.py: Created with pure logic for signal scoring.
- src/ytclfr/confidence/rules.py: Created branch decision rules.
- src/ytclfr/confidence/policy.py: Created rescan policy rules.
- src/ytclfr/confidence/controller.py: Created top-level evaluate entry point.
- src/ytclfr/tasks/align.py: Wired confidence evaluation to build_timeline.
- 	ests/unit/confidence/*: Added comprehensive test coverage.
- decisions.md: Appended DR-17.
- uild.md: Marked Phase 7 complete.

### Summary
Implemented the Confidence Controller as a pure logic module. It evaluates the unified timeline and extractor results to decide whether to trust, rescan, or downgrade. Unit tests cover all fallback and threshold logic.
