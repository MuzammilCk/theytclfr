# decisions.md

## Format Reference

Each architectural decision uses this format:

## DR-[N] Ã¢â‚¬â€� [decision title]
Date: [YYYY-MM-DD]
Status: ACCEPTED / SUPERSEDED / UNDER REVIEW
Context: [why this decision was needed]
Decision: [exactly what was decided]
Consequences: [what this enables and what it rules out]
Supersedes: [DR-N if applicable, else NONE]

---

## DR-1 Ã¢â‚¬â€� Primary database choice
Date: 2026-04-20
Status: SUPERSEDED by DR-1-REV
Context: The system needs a primary relational database to store job records, video metadata, transcript segments, OCR results, aligned timelines, structured extraction output, and confidence scores. The database must support JSONB for flexible structured data storage and the pgvector extension for future vector/semantic search capability. It must run on a single laptop alongside all other services.
Decision: PostgreSQL 16 as the primary relational database. All persistent application data is stored here. The pgvector extension is installed for vector similarity search. Alembic is used for schema migrations.
Consequences: Enables relational integrity, JSONB flexibility, and vector search in a single database engine. Rules out NoSQL-first approaches. Requires PostgreSQL to be running locally (native install). All future schema changes must use Alembic migrations.
Supersedes: NONE

## DR-1-REV Ã¢â‚¬â€� Primary database choice (revised)
Date: 2026-04-20
Status: ACCEPTED
Context: Local PostgreSQL installation on Windows/WSL adds
  setup friction and consumes RAM on a laptop already running
  Ollama, faster-whisper, Celery, and Redis simultaneously.
  Supabase provides a hosted PostgreSQL 16 instance with
  pgvector pre-installed, eliminating both issues.
Decision: Supabase hosted PostgreSQL satisfies the PostgreSQL
  16 requirement. The DATABASE_URL in .env points to the
  Supabase connection string. All application code
  (SQLAlchemy, Alembic, psycopg2-binary) is unchanged.
  pgvector extension is enabled via the Supabase dashboard,
  not via migration SQL.
Consequences: Removes local PostgreSQL as a dependency.
  Requires a Supabase account and project. The free tier
  is sufficient for V1. Alembic migrations run against the
  Supabase database the same way they would run locally.
  Section 1.7 of context.md is updated to reflect that
  the database runs on Supabase, not on the laptop.
Supersedes: DR-1

---

## DR-2 Ã¢â‚¬â€� Task queue and worker system
Date: 2026-04-20
Status: ACCEPTED
Context: Video processing involves multiple long-running steps (download, ASR, OCR, LLM calls) that cannot run in the API request cycle. A task queue is needed to enqueue jobs from the FastAPI API and execute them asynchronously in worker processes. The system runs on a single laptop, so the solution must be lightweight.
Decision: Celery 5 as the task queue and worker framework with Redis as the message broker. Tasks are defined per pipeline stage (download, transcribe, extract OCR, classify, structure, score). Celery runs as a separate process on the same machine as the API.
Consequences: Enables async job processing with task chaining, retries, and status tracking. Redis serves double duty as both message broker and application cache. Rules out in-process async-only approaches (which cannot survive API restarts). Requires Redis to be running locally.
Supersedes: NONE

---

## DR-3 Ã¢â‚¬â€� Temporary media storage strategy
Date: 2026-04-20
Status: ACCEPTED
Context: Downloaded YouTube videos and extracted audio files need temporary storage during processing. After all extraction steps (ASR, OCR) are complete, the media files must be deleted. The system runs on a single laptop Ã¢â‚¬â€� cloud storage (S3) adds unnecessary complexity for V1.
Decision: Local filesystem storage at the path specified by the TEMP_MEDIA_PATH environment variable. Files are organized by job_id in subdirectories. Cleanup is triggered after all extraction tasks for a job complete. TEMP_MEDIA_MAX_AGE_SECONDS provides a safety net for orphaned files.
Consequences: Enables simple, fast I/O for video processing on a single machine. Rules out S3-compatible storage in V1 (deferred to future multi-machine deployment). Requires sufficient local disk space for concurrent video downloads. Media files are ephemeral Ã¢â‚¬â€� the system is NOT a video hosting or storage service.
Supersedes: NONE

---

## DR-4 Ã¢â‚¬â€� LLM/AI provider choice
Date: 2026-04-20
Status: ACCEPTED
Context: The system uses LLMs to parse aligned timeline content (ASR + OCR) and extract structured data (recipes, movie lists, scripts, etc.). Two tiers of LLM capability are needed: a local model for routine extraction tasks and a cloud model for hard reasoning tasks requiring higher accuracy or longer context windows.
Decision: Two-tier LLM strategy. Tier 1 (local): Ollama running llama3.1:8b on the same laptop Ã¢â‚¬â€� used for routine extraction, classification support, and simple structuring tasks. Tier 2 (cloud): Groq API running llama-3.3-70b-versatile Ã¢â‚¬â€� used for hard reasoning tasks, complex multi-item extraction, and fallback when local model confidence is low. Escalation logic: try Ollama first, escalate to Groq when local results fail parsing or fall below confidence threshold.
Consequences: Enables cost-effective local processing for most tasks while retaining access to a more powerful model for difficult cases. Rules out OpenAI, Anthropic, and other commercial LLM providers in V1. Requires Ollama to be installed and running locally with the llama3.1:8b model pulled. Requires a valid GROQ_API_KEY for cloud escalation. Groq usage incurs API costs on their pay-as-you-go plan.
Supersedes: NONE

---

## DR-5 Ã¢â‚¬â€� OCR engine choice
Date: 2026-04-20
Status: ACCEPTED
Context: The system needs to extract on-screen text from video frames Ã¢â‚¬â€� titles, overlays, ingredient lists, graphics, captions rendered into the video itself (not subtitle tracks). The OCR engine must run locally on a CPU-only laptop with no external API dependency.
Decision: Tesseract 5 via the pytesseract Python wrapper. Video frames are sampled at a configurable rate (OCR_FRAME_SAMPLE_RATE env var), extracted using ffmpeg, and passed to Tesseract for text recognition. Adjacent duplicate text is deduplicated to avoid repeating static overlays.
Consequences: Enables local, offline OCR with no API cost. Tesseract handles Latin-script languages well out of the box. Rules out cloud OCR services (Google Vision, AWS Textract) in V1. Accuracy on stylized or low-contrast text may be limited Ã¢â‚¬â€� this is an acceptable tradeoff for V1. May require Tesseract language packs for non-English videos.
Supersedes: NONE

---

## DR-6 Ã¢â‚¬â€� ASR / transcript engine choice
Date: 2026-04-20
Status: ACCEPTED
Context: The system needs to transcribe spoken content from YouTube videos with word-level timestamps. The ASR engine must run locally on a CPU-only laptop with no external API dependency. Accuracy must be sufficient for downstream LLM structuring Ã¢â‚¬â€� the transcript does not need to be publishing-quality, but must be good enough for entity extraction.
Decision: faster-whisper with model=small and device=cpu. This is a confirmed decision. faster-whisper is a CTranslate2-optimized implementation of OpenAI Whisper, providing significantly faster CPU inference than the original Whisper. The small model balances accuracy and CPU performance. Word-level timestamps are extracted for provenance tracking.
Consequences: Enables local, offline ASR with no API cost. CPU inference with model=small is viable on a modern laptop (expected ~2-4x slower than real-time). Rules out cloud ASR services (Google STT, AWS Transcribe, AssemblyAI) in V1. Rules out larger Whisper models (medium, large) due to CPU performance constraints. Accuracy on heavily accented or multi-speaker audio may be limited.
Supersedes: NONE

---

## DR-7 Ã¢â‚¬â€� Authentication mechanism
Date: 2026-04-20
Status: SUPERSEDED by DR-7-REV
Context: The output API must be protected to prevent unauthorized access to job submission and result retrieval. The auth mechanism must be stateless (no server-side session storage), simple to implement, and suitable for both developer API usage and frontend UI authentication.
Decision: JWT (JSON Web Tokens) with HS256 signing. Protected endpoints: POST /api/v1/jobs, GET /api/v1/jobs/{job_id}, GET /api/v1/jobs/{job_id}/result. Unprotected endpoints: GET /api/v1/health, GET /docs, GET /openapi.json, static frontend assets. JWT secret is stored in JWT_SECRET_KEY env var. Token expiry is configurable via JWT_EXPIRY_MINUTES. No refresh token mechanism in V1.
Consequences: Enables stateless authentication suitable for API and UI consumers. Rules out OAuth2 flows (deferred to future version if third-party integrations are needed). Rules out API key authentication (less flexible than JWT). No user registration or login flow is defined in V1 Ã¢â‚¬â€� token generation mechanism is left to Phase 2 implementation (could be a simple admin-generated token or a basic login endpoint).
Supersedes: NONE

## DR-7-REV Ã¢â‚¬â€� Authentication mechanism (revised)
Date: 2026-04-20
Status: ACCEPTED
Context: The output API must be protected. Building custom user registration and login flows is unnecessary when Supabase provides a fully managed authentication service that issues standard JWTs.
Decision: Phase 3 will validate Supabase-issued JWTs using the Supabase JWT secret. We are not building custom token generation, user registration, or login endpoints. The FastAPI auth dependency reads the JWT secret from the JWT_SECRET_KEY environment variable Ã¢â‚¬â€� which will be the Supabase JWT secret from the dashboard, not a custom-generated one.
Consequences: Simplifies the backend by removing user management. The python-jose library is still used. Nothing in pyproject.toml changes. Our API will trust tokens signed by Supabase.
Supersedes: DR-7

---

## DR-8 Ã¢â‚¬â€� Schema validation approach
Date: 2026-04-20
Status: ACCEPTED
Context: The system needs robust runtime validation for API request/response payloads, database models, LLM output parsing, and structured extraction schemas. The validation library must integrate naturally with the chosen API framework (FastAPI) and support JSON Schema generation for API documentation.
Decision: Pydantic v2 for all schema validation. Request models validate incoming API payloads. Response models define the structured JSON output schema. Internal models validate LLM output parsing results. Pydantic's JSON Schema generation powers the OpenAPI documentation. Strict mode is used where applicable to catch type coercion issues.
Consequences: Enables type-safe validation across the entire pipeline with minimal boilerplate. FastAPI's native Pydantic integration means request/response validation is automatic. Rules out JSON Schema (manual, no Python type integration), Protobuf (unnecessary complexity for a REST API), and marshmallow (redundant with Pydantic + FastAPI).
Supersedes: NONE

---

## DR-9 Ã¢â‚¬â€� Search and retrieval layer
Date: 2026-04-20
Status: ACCEPTED
Context: The system needs to support searching across extracted content Ã¢â‚¬â€� finding specific segments, items, or timestamps within processed videos. A dedicated search layer enables future features like cross-video search and semantic similarity queries. The V1 deployment is single-machine, so a separate search cluster (OpenSearch/Elasticsearch) adds significant resource overhead.
Decision: pgvector extension within PostgreSQL for V1. Vector embeddings are stored alongside extracted content in PostgreSQL. GIN indexes support full-text search on transcript and OCR text. Semantic similarity search uses pgvector's cosine distance operator. No separate OpenSearch or Elasticsearch cluster in V1. SCOPE REVIEW: OpenSearch may be added in a future version for cross-video search at scale, but is deferred from V1 to keep the single-machine footprint minimal.
Consequences: Enables both full-text and vector similarity search within the existing PostgreSQL database. No additional service to manage or monitor. Rules out OpenSearch/Elasticsearch in V1 (deferred). Search performance is bounded by PostgreSQL capabilities Ã¢â‚¬â€� acceptable for V1 single-user/small-team usage. Embedding generation requires a model (could use Ollama or a lightweight sentence-transformer Ã¢â‚¬â€� to be decided in Phase 7).
Supersedes: NONE

---
Consequences: Enables both full-text and vector similarity search within the existing PostgreSQL database. No additional service to manage or monitor. Rules out OpenSearch/Elasticsearch in V1 (deferred). Search performance is bounded by PostgreSQL capabilities Ã¢â‚¬â€ acceptable for V1 single-user/small-team usage. Embedding generation requires a model (could use Ollama or a lightweight sentence-transformer Ã¢â‚¬â€ to be decided in Phase 7).
Supersedes: NONE

---

## DR-10 Ã¢â‚¬â€ Task queue and worker system choice
Date: 2026-04-20
Status: ACCEPTED
Context: This decision elaborates on DR-2 by specifying the worker execution strategy and task orchestration model. The pipeline has multiple sequential stages (download Ã¢â€ â€™ ASR Ã¢â€ â€™ OCR Ã¢â€ â€™ align Ã¢â€ â€™ classify Ã¢â€ â€™ LLM structure Ã¢â€ â€™ confidence score) that must execute in order for each job, with some stages (ASR, OCR) potentially running in parallel.
Decision: Celery task chains and chords for pipeline orchestration. Sequential stages are linked via Celery chains. ASR and OCR tasks run in parallel via a Celery chord, with the temporal alignment task as the chord callback. Worker concurrency is controlled via WORKER_CONCURRENCY env var. Task time limits are enforced via CELERY_TASK_TIME_LIMIT. Failed tasks update job status and halt the pipeline for that job. No automatic retry of the full pipeline Ã¢â‚¬â€ individual task retries are configured per task.
Consequences: Enables parallel execution of ASR and OCR stages while maintaining sequential ordering for dependent stages. Celery's built-in retry, timeout, and error handling mechanisms reduce custom orchestration code. Rules out custom pipeline orchestration frameworks. Rules out fully parallel execution of all stages (some stages depend on outputs of prior stages). Pipeline monitoring is available through Celery's built-in inspection API.
Supersedes: NONE (extends DR-2 with execution strategy details)

## DR-12 Ã¢â‚¬â€ Rate limiting library
Date: 2026-04-20
Status: ACCEPTED
Context: Phase 3 requires rate limiting on the job submission and status endpoints to prevent abuse. A lightweight library that integrates natively with FastAPI/Starlette is needed.
Decision: slowapi added to pyproject.toml. IP-based rate limiting in Phase 3. Per-user rate limiting can be added in Phase 9 using the authenticated identity from the JWT payload.
Consequences: Adds one dependency. Limits are per IP in V1, not per authenticated user. Rate limit headers are automatically included in responses.
Supersedes: NONE

---

## DR-11 â€” YouTube cookie authentication strategy
Date: 2026-04-21
Status: ACCEPTED
Context: YouTube's bot detection system rejects all
  unauthenticated yt-dlp requests since mid-2024.
  Chrome cookies cannot be decrypted on Windows since
  Chrome 127. Firefox stores cookies in plain SQLite
  without encryption and is the only reliable cookie
  source for yt-dlp on Windows in 2026.
Decision: yt-dlp reads a cookies.txt file in Netscape
  format exported from Firefox. File path set via
  YTDLP_COOKIES_FILE env var (optional, defaults to
  None). Excluded from git. Cookies must be refreshed
  approximately every 2 weeks.
Consequences: Downloads succeed on most YouTube
  videos. Requires Firefox and periodic refresh.
  cookies.txt must never be committed.
Supersedes: NONE
## DR-12 Ã¢â‚¬â€� Phase 4 router bug-fix: yt-dlp metadata format
Date: 2026-04-21
Status: ACCEPTED
Context: Session 10 implemented check_audio_from_metadata()
  expecting ffprobe JSON (streams[], format.duration).
  downloader.py stores the yt-dlp info dict which has no
  "streams" key and stores duration as a top-level float,
  not under "format". Audio detection returned False for
  100% of videos. Additionally, LIST_KEYWORDS contained
  single-word tokens ("best", "all", "top") matched with
  simple substring search, causing music videos with
  common English words in titles to misroute as list-edit.
  "tutorial" appeared in both RECIPE_KEYWORDS and
  SLIDE_KEYWORDS causing double-flagging. The duration
  gate (60-600s) in likely_music excluded ringtones and
  YouTube Shorts from music detection.
Decision:
  1. check_audio_from_metadata() reads yt-dlp fields:
     acodec, abr, subtitles. Duration gate moved to
     classifier (MUSIC_MIN_DURATION_SECONDS = 10.0s).
  2. LIST_KEYWORDS replaced with multi-word phrases only.
     Word-boundary regex (re.search with \b) used for all
     keyword matching. Tags included in normalized text.
  3. "tutorial" removed from RECIPE_KEYWORDS. It remains
     in SLIDE_KEYWORDS only.
  4. Classifier Rule 1 guard changed from
     "NOT has_list_signal" to "NOT has_recipe_signal".
     Music with superlatives in the title now correctly
     routes as music-heavy.
  5. Unit tests rewritten to use yt-dlp format inputs.
Consequences: Router correctly classifies music content
  regardless of title wording. Ringtones, Shorts, and
  long recordings all route correctly. List-edit routing
  requires genuine multi-word list phrases.
Supersedes: NONE. Corrects implementation of DR-10.

## DR-13 Ã¢â‚¬â€� Extractor task base class pattern
Date: 2026-04-21
Status: ACCEPTED
Context: Phase 5 adds three new Celery extractor tasks (ASR, OCR, audio classifier). Each task needs identical retry policy (max_retries=3, retry_backoff), structured on_failure and on_retry logging, and failure isolation. Copy-pasting this boilerplate into three tasks creates maintenance risk.
Decision: A BaseExtractorTask(Task) class in extractors/base.py provides shared on_failure() and on_retry() hooks with structured logging. All extractor tasks set base=BaseExtractorTask in their decorator. Individual extractors (ASR, OCR, audio) are implemented as plain Python classes (not Celery tasks). Celery task wrappers in tasks/extract.py call the extractor classes. This keeps the extractor logic independently testable without Celery overhead.
Consequences: Extractor logic is fully testable without Celery. New extractors (YAMNet, object detection) added in V2 follow the same pattern. BaseExtractorTask is abstract=True so it cannot be used as a task itself.
Supersedes: NONE

## DR-14 â€” Celery task DB session pattern (context manager)
Date: 2026-04-22
Status: ACCEPTED
Context: All Celery tasks were using a generator-based session
  acquisition pattern (db_gen = get_db(); session = next(db_gen))
  that left the generator's internal finally block unexecuted,
  causing memory and connection leaks in long-running workers.
Decision: All Celery tasks use the db_session() context manager
  exclusively. get_db() remains for FastAPI dependency injection
  only. db_session() is the single approved pattern for use in
  Celery tasks, scripts, and any non-FastAPI context.
Consequences: Generator leaks eliminated. Session lifecycle is
  guaranteed by the context manager's finally block. No manual
  session.close() calls in task code.
Supersedes: NONE

## DR-15 â€” Property-based testing with hypothesis
Date: 2026-04-22
Status: ACCEPTED
Context: Phase 6 temporal alignment layer requires property-based
  tests for overlap edge cases per the architecture plan. The
  hypothesis library is the standard Python property-based testing
  framework and integrates natively with pytest.
Decision: hypothesis added to pyproject.toml dev dependencies.
  Used exclusively in Phase 6 alignment overlap tests. Not a
  runtime dependency.
Consequences: Adds one dev-only dependency. Enables exhaustive
  edge-case testing for interval merge logic. No runtime impact.
Supersedes: NONE

## DR-16 â€” Temporal alignment as pure computation module
Date: 2026-04-22
Status: ACCEPTED
Context: Phase 6 builds the temporal alignment layer. The
  alignment logic could be embedded in the Celery task or
  extracted as a standalone module. Embedding couples the
  logic to Celery and makes it untestable without task
  infrastructure.
Decision: Alignment logic lives in src/ytclfr/alignment/ as
  pure Python functions with zero Celery or DB dependencies.
  The existing build_timeline Celery task in tasks/align.py
  calls alignment.engine.align() and handles DB status
  updates. This separation mirrors the extractor pattern
  from DR-13.
Consequences: Alignment logic is fully testable without
  Celery or DB. Pure functions are deterministic and
  reproducible. The Celery task is a thin wrapper only.
Supersedes: NONE

## DR-17 â€” Confidence Controller as pure logic module
Date: 2026-04-23
Status: ACCEPTED
Context: Phase 7 builds the confidence controller that decides
  whether to trust, rescan, or downgrade pipeline results.
  The controller could be embedded in the Celery task or
  extracted as a standalone module. Embedding couples scoring
  logic to task infrastructure and makes it untestable.
Decision: Confidence logic lives in src/ytclfr/confidence/ as
  pure Python functions with zero Celery, DB, or queue
  dependencies. The existing build_timeline task in
  tasks/align.py calls confidence.controller.evaluate() and
  handles any rescan dispatch. This mirrors the patterns
  established in DR-13 (extractors) and DR-16 (alignment).
Consequences: Confidence scoring is fully testable without
  infrastructure. All thresholds are TUNABLE module-level
  constants. The controller never writes to DB or enqueues
  tasks directly. Rescan dispatch is deferred to Phase 8.
Supersedes: NONE

---

## DR-18 â€” Replace local storage with S3 object storage
Date: 2026-04-24
Status: ACCEPTED
Context: The V1 architecture (DR-3) used local filesystem storage
  at TEMP_MEDIA_PATH. In a distributed Kubernetes deployment with
  multiple Celery worker nodes, the ingestion worker downloads the
  video to its local disk, but the ASR/OCR workers run on different
  nodes and cannot access that path. Local filesystem transport is
  a catastrophic bottleneck for distributed scaling.
Decision: After download, the ingestion task uploads the video to
  S3 with object key `{job_id}/video.mp4` via boto3, stores the
  S3 URI in `job.s3_video_uri`, and immediately deletes the local
  file. Extraction tasks download the video from S3 to a transient
  local path before processing and delete it in a `finally` block.
  `job.local_media_path` is set to None after S3 upload.
Consequences: Workers are fully stateless with respect to media
  files. Requires AWS credentials and an S3 bucket. boto3 added
  to frozen stack. DR-3 local-only strategy is superseded for
  production deployments.
Supersedes: DR-3

## DR-19 â€” Heterogeneous Celery queue topology
Date: 2026-04-24
Status: ACCEPTED
Context: V1 used two queues (fast, heavy) on a single machine
  (DR-2, DR-10). In a distributed deployment, different worker
  types need different resource profiles: ingest workers need
  network bandwidth, ASR/OCR workers need CPU/GPU, and fast
  workers need minimal resources.
Decision: The queue topology remains `fast` and `heavy` but
  workers are deployed as separate Kubernetes node pools with
  different resource allocations. The Celery app configuration
  supports this without code changes â€” only deployment manifests
  change. Tasks are already assigned to queues via their decorators.
Consequences: Horizontal scaling per worker type is possible.
  No code changes required beyond what DR-18 enables (S3 transport).
  Deployment manifests (Phase 9) will define the node pool specs.
Supersedes: DR-2, DR-10 (extends, does not invalidate)

## DR-20 â€” Database-backed Celery chord payloads
Date: 2026-04-24
Status: ACCEPTED
Context: The V1 chord pattern (DR-10) returned full
  ExtractorResult.model_dump(mode="json") from each extractor
  task. These payloads (ASR transcripts, OCR results) can be
  50MB+ and are serialized through Redis as chord arguments.
  This causes Redis OOM evictions under load and wastes bandwidth.
Decision: Extractor tasks return only a lightweight status dict:
  `{"job_id": str, "extractor_type": str, "status": str}`.
  The full results are already persisted to the `extractor_results`
  Postgres table by each task. The `build_timeline` chord callback
  queries `extractor_results` from Postgres by job_id instead of
  reading from the chord arguments.
Consequences: Redis memory usage drops dramatically. Chord
  payloads are ~100 bytes instead of ~50MB. Alignment engine
  `align()` function signature is unchanged â€” it still receives
  `list[dict]`, but the data is fetched from DB inside
  `build_timeline` instead of passed through Redis.
Supersedes: NONE (refines DR-10 chord pattern)

## DR-21 — Embedding via Ollama
Date: 2026-04-24
Status: ACCEPTED
Context: Phase 8 requires vector embeddings for semantic similarity search over aligned video segments. The system already uses Ollama for local LLM inference (DR-4).
Decision: We use the existing local Ollama instance for embedding generation, using the nomic-embed-text model. The embedding dimension is configured via EMBEDDING_DIM (default 768). Embeddings are clamped to this dimension before persistence.
Consequences: Enables semantic search without external API dependencies. Reuses existing local infrastructure.

## DR-22 — Postgres GIN search
Date: 2026-04-24
Status: ACCEPTED
Context: Phase 8 requires full-text keyword search over aligned video segments. V1 architecture limits the introduction of new large services like Elasticsearch (DR-9).
Decision: Full-text search is implemented using Postgres GIN indexes and the to_tsvector function natively in Postgres.
Consequences: Provides robust full-text search without needing a separate search cluster. Maintains the single-database deployment strategy.

## DR-23 — Lightweight Observability & DLQ
Date: 2026-04-24
Status: ACCEPTED
Context: Phase 9 end-to-end hardening requires tracing and retry mechanisms without introducing heavy external dependencies (Prometheus, Grafana, Jaeger) per the frozen stack constraint.
Decision: We use Python's built-in contextvars to inject a 	race_id (usually the job_id) across logs in FastAPI and Celery. Pipeline metrics are served via a lightweight PostgreSQL query endpoint (GET /api/v1/metrics). Dead Letter Queue (DLQ) is implemented logically by transitioning exhausted retries to a dead_letter status in the DB, allowing the new /retry endpoint to recover jobs from partial checkpoints using idempotency logic.
Consequences: High observability and fault tolerance achieved within existing infrastructure. No new deployments needed.

---

## DR-V2-01 — Evidence-Based Late Binding replaces RouterDecision
Date: 2026-05-23
Status: ACCEPTED
Context: V1 RouterDecision forces a single content-type label before content analysis runs. This produces incorrect output when signals do not match the title heuristic.
Decision: V1 contracts/router.py and router/classifier.py are deprecated. Stage A produces a SignalManifest — a multi-signal evidence object — with no content-type classification. Classification runs only in Stage D after all evidence exists.
Consequences: No extractor runs before a manifest exists. The manifest drives Stage B's dynamic Celery group. V1 tables remain until a cleanup migration removes them after V2 is live.
Supersedes: NONE

---

## DR-V2-02 — Probers are pure functions with no infrastructure deps
Date: 2026-05-23
Status: ACCEPTED
Context: probe_audio, probe_visual, and probe_metadata could be written as Celery tasks or as plain functions. Making them Celery tasks adds broker overhead and makes unit testing harder.
Decision: All three probers are pure functions that accept file paths and return dataclass results. The single Celery task `run_signal_census` orchestrates them sequentially. This keeps probing logic testable without Redis/PostgreSQL infrastructure.
Consequences: Probers run in-process inside the Celery worker. They cannot be distributed across multiple workers. This is acceptable because probe_audio and probe_visual together complete in < 90s on the ThinkPad L13.
Supersedes: NONE

---

## DR-V2-03 — Windows-compatible timeout via threading.Timer
Date: 2026-05-23
Status: ACCEPTED
Context: The original design used `signal.alarm()` for timeout guards in probe_audio and probe_visual. `signal.alarm()` is not available on Windows, which is the primary development platform (ThinkPad L13).
Decision: Replace `signal.alarm()` with `threading.Timer` + `threading.Event` for timeout detection. A daemon timer sets an event flag; each major probe step checks the flag and raises an internal `_TimeoutError` if set.
Consequences: Timeout granularity is limited to the check points between probe steps (not truly preemptive). A single long-running OpenCV or librosa call cannot be interrupted mid-operation. This is acceptable because each individual operation has its own subprocess timeout (ffprobe: 30s, ffmpeg: 60s) or data cap (librosa: duration=60.0s).
Supersedes: NONE

---

## DR-V2-04 — Structural Metadata is a Weak Prior, Video Structure is Inferred
Date: 2026-05-26
Status: ACCEPTED
Context: Initially, metadata (like channel names or video titles) was considered enough to dictate structural taxonomy. However, a mature system should infer structure directly from the media (OCR, ASR) and treat metadata as a cheap prior.
Decision: Structural mapping is late-bound. Stage C fuses OCR, ASR, and visual evidence to confidently detect structural types (e.g., list, ranking, compilation). Stage D then uses these structural types as hard overrides for taxonomy classification, instead of relying purely on metadata.
Consequences: Requires OCR to be prioritized when structure is likely. Conflict resolver favors OCR for structured videos and ASR for non-structured speech-heavy videos.
Supersedes: NONE

## DR-V2-11 - Removed StructuralDetector in favor of pattern scoring
Date: 2026-05-27
Status: ACCEPTED
Context: The mock \StructuralDetector\ class was outdated and unmaintainable.
Decision: Deleted \StructuralDetector\ and completely replaced its heuristic logic within \ocr_pattern_scorer.py\ and \manifest_store.py\. Stage B OCR gating handles dispatcher behavior.
Consequences: Structural detection is now fully pattern-driven using OCR ordinal metrics and countdowns instead of rigid object-oriented classes.

## DR-V2-12 - ASR expected value discount
Date: 2026-05-27
Status: ACCEPTED
Context: Heavy-structural videos often contain misleading ASR segments that distract from the core visual information.
Decision: Applied \sr_expected_value\ linearly against ASR confidence during fusion in \conflict_resolver.py\.
Consequences: ASR outputs with low structural expectancy are suppressed, improving taxonomy precision in listicle formats.

## DR-V2-13 — NumPy scalar sanitization for SSE events
Date: 2026-05-27
Status: ACCEPTED
Context: Session 29 audit identified that numpy scalars from
  OpenCV/librosa survive Pydantic model_dump(mode="json") but
  crash json.dumps() in _emit_sse(), silently dropping all
  SSE progress events.
Decision: A _sanitize_for_json() recursive converter is applied
  in every _emit_sse() function across all 4 stages. Defense-in-
  depth: probe result constructors also cast numpy values to
  native Python types.
Consequences: SSE events are never silently dropped due to
  numpy types. The sanitizer adds <1ms overhead per event.
Supersedes: NONE

## DR-V2-14 — Tiered text density scoring in structural detector
Date: 2026-05-27
Status: ACCEPTED
Context: Session 29 audit found overlay_text_density=103.9
  scored identically to density=2.1 (both +0.30). Extreme text
  density alone could not trigger OCR.
Decision: Two-tier density: >15.0 (EXTREME) scores +0.60,
  >2.0 (HIGH) scores +0.30. MOTION_DENSITY_HIGH lowered from
  10.0 to 7.5. New MOTION_DENSITY_MODERATE at 4.0 (+0.10).
Consequences: Pure text-wall videos self-trigger OCR. Short
  listing videos with 2-3 cuts also trigger. No false positives
  expected because 15+ text regions/frame is unambiguous.
Supersedes: NONE

## DR-V2-15 — ALL-CAPS entity extraction
Date: 2026-05-27
Status: ACCEPTED
Context: Session 29 audit found entity extractor regex only
  matched Title-Case phrases. Music chart videos display all
  artist names and song titles in ALL CAPS.
Decision: Added ALL_CAPS_PHRASE regex and RANKED_ITEM_PATTERN
  for explicit list item parsing. Stop-word filter prevents
  noise from common UI text (SUBSCRIBE, VIEWS, etc).
Consequences: ALL-CAPS entities now contribute to the entity
  pool. Ranked items are directly extracted as high-confidence
  entities.
Supersedes: NONE

## DR-V2-16 — Priority transcript for structural Groq prompts
Date: 2026-05-27
Status: ACCEPTED
Context: Session 29 audit found 8000-char transcript cap hid
  55 of 60 songs. OCR ranked items were buried after verbose
  ASR commentary.
Decision: Structural videos use a 16000-char priority transcript
  that prepends OCR ranked items before chronological segments.
  Non-structural videos keep the 8000-char standard path.
Consequences: Groq sees the full ranked item list for long
  structural videos. Prompt cost doubles for structural videos
  (~negligible at current volume).
Supersedes: NONE

## DR-V2-17 — Adaptive burned-in text threshold for short videos
Date: 2026-05-27
Status: ACCEPTED
Context: TEXT_REGION_MIN_FRAMES=5 makes has_burned_in_text
  mathematically impossible for videos with <5 sampled frames.
  Short listing videos never trigger OCR through this path.
Decision: Adaptive threshold: min(5, max(1, len(frames) // 2)).
  For 30-frame videos, unchanged (5). For 3-frame videos,
  threshold drops to 1.
Consequences: Short listing videos can now trigger OCR via
  has_burned_in_text. Very short videos (2-3 frames) have
  a lower bar — acceptable because these are typically
  dense info cards.
Supersedes: NONE

---

## DR-V3-01 — V3 Strict Contract Isolation
Date: 2026-05-28
Status: ACCEPTED
Context: V2 mixed contracts and mutable states caused tracking issues.
Decision: All V3 contracts use `frozen=True`. V1/V2 contracts deprecated. V3 contracts live in `contracts/v3/`.
Consequences: Hard isolation prevents accidental mutation of states.

## DR-V3-02 — Resource Views over Boolean Flags
Date: 2026-05-28
Status: ACCEPTED
Context: API responses needed a way to control verbosity.
Decision: API uses `?view=BASIC|FULL` instead of `?include_debug=true`.
Consequences: Scales for future views like EMBEDDINGS.

## DR-V3-03 — ASR Degradation Detection
Date: 2026-05-28
Status: ACCEPTED
Context: Poor ASR quality caused issues in inference.
Decision: `ASRCompletenessMetrics` computes `untranscribed_speech_ratio`. If >0.3 or `max_untranscribed_segment_ms` > 2500, OCR weight is boosted in conflict resolution.
Consequences: Mitigates impact of bad audio transcription automatically.

## DR-V3-04 — Structured JSON Evidence Prompts
Date: 2026-05-28
Status: ACCEPTED
Context: Plain text summaries limited Groq's ability to reason over complex evidence.
Decision: Groq receives full `EvidenceGraph` as structured JSON, not text summaries.
Consequences: Better reasoning capabilities for complex tasks at the cost of larger prompt sizes.

## DR-V3-05 — V3 Celery Task Registration
Date: 2026-05-28
Status: ACCEPTED
Context: V3 tasks weren't being picked up by Celery.
Decision: V3 tasks registered via explicit imports in `celery_app.py`. No autodiscovery.
Consequences: Hard dependency on explicit registration prevents accidental misconfigurations.

## DR-V3-06 — Metadata Pruning at Ingestion
Date: 2026-05-28
Status: ACCEPTED
Context: yt-dlp metadata fields were excessively large, causing DB bloat and celery serialization issues.
Decision: yt-dlp `formats`, `thumbnails`, `heatmap` stripped. `automatic_captions`/`subtitles` reduced to language keys only.
Consequences: Drastically reduces metadata payload size while preserving structural hints.


## DR-V4-01 - Shadow Pipeline Architecture for Advanced ML Models
Date: 2026-05-28
Status: ACCEPTED
Context: Replacing stable legacy extractors (Tesseract, OpenCV samplers, FFprobe) directly with heavy, complex dependencies (PaddleOCR, PyAV, VLMs) poses catastrophic risk to production if a single library crashes.
Decision: New modules are built as parallel, isolated files rather than overwriting legacy code. A 10% shadow traffic router was introduced at the API ingestion endpoint (v3/jobs) to test these models asynchronously against real production workloads, discarding the output to the user.
Consequences: Legacy pipeline stability is preserved 100%. Infrastructure footprint will increase to support the heavy queue processing for shadow tasks. Safe benchmarking of PaddleOCR and VLM taxonomy can proceed.


## DR-V4-02 - ffmpeg image2pipe for Frame Sampling
Date: 2026-05-28
Status: ACCEPTED
Context: cv2.VideoCapture seeking (CAP_PROP_POS_FRAMES) causes O(N) keyframe decodes on H.264/H.265 video, leading to massive CPU regression and timeout errors.
Decision: Frame sampling now pipes directly from ffmpeg using image2pipe and bgr24 format.
Consequences: ~80% reduction in processing time for Stage A visual probing.

## DR-V4-03 - Async Connection Pooling for Ollama
Date: 2026-05-28
Status: ACCEPTED
Context: Generating embeddings segment-by-segment blocked the Celery worker for minutes using synchronous httpx requests.
Decision: Embedding generation uses asyncio and httpx.AsyncClient with a concurrency semaphore (max 20) inside the Celery worker.
Consequences: Drastically reduces embedding generation time. Celery workers must not block the event loop if using gevent/eventlet pools.

## DR-V4-04 - Rotating Cookie Pool for yt-dlp
Date: 2026-05-28
Status: ACCEPTED
Context: A single cookies.txt file gets banned rapidly under production load.
Decision: Implemented `CookiePool` which scans a `cookies/` directory and distributes files round-robin using thread-safe locking.
Consequences: yt-dlp bans are amortized across multiple accounts.

## DR-V4-05 - Native Python Casting vs Recursive Sanitization
Date: 2026-05-28
Status: ACCEPTED
Context: The `_sanitize_for_json` recursive function fired on every SSE event, creating huge CPU overhead for nested EvidenceGraph payloads.
Decision: Dropped recursive sanitization. All numpy arrays and metrics must be explicitly cast to native int/float at creation time in the prober/extractor.
Consequences: Near-zero CPU overhead during SSE emission.
