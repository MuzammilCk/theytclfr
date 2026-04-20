# decisions.md

## Format Reference

Each architectural decision uses this format:

## DR-[N] — [decision title]
Date: [YYYY-MM-DD]
Status: ACCEPTED / SUPERSEDED / UNDER REVIEW
Context: [why this decision was needed]
Decision: [exactly what was decided]
Consequences: [what this enables and what it rules out]
Supersedes: [DR-N if applicable, else NONE]

---

## DR-1 — Primary database choice
Date: 2026-04-20
Status: SUPERSEDED by DR-1-REV
Context: The system needs a primary relational database to store job records, video metadata, transcript segments, OCR results, aligned timelines, structured extraction output, and confidence scores. The database must support JSONB for flexible structured data storage and the pgvector extension for future vector/semantic search capability. It must run on a single laptop alongside all other services.
Decision: PostgreSQL 16 as the primary relational database. All persistent application data is stored here. The pgvector extension is installed for vector similarity search. Alembic is used for schema migrations.
Consequences: Enables relational integrity, JSONB flexibility, and vector search in a single database engine. Rules out NoSQL-first approaches. Requires PostgreSQL to be running locally (native install). All future schema changes must use Alembic migrations.
Supersedes: NONE

## DR-1-REV — Primary database choice (revised)
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

## DR-2 — Task queue and worker system
Date: 2026-04-20
Status: ACCEPTED
Context: Video processing involves multiple long-running steps (download, ASR, OCR, LLM calls) that cannot run in the API request cycle. A task queue is needed to enqueue jobs from the FastAPI API and execute them asynchronously in worker processes. The system runs on a single laptop, so the solution must be lightweight.
Decision: Celery 5 as the task queue and worker framework with Redis as the message broker. Tasks are defined per pipeline stage (download, transcribe, extract OCR, classify, structure, score). Celery runs as a separate process on the same machine as the API.
Consequences: Enables async job processing with task chaining, retries, and status tracking. Redis serves double duty as both message broker and application cache. Rules out in-process async-only approaches (which cannot survive API restarts). Requires Redis to be running locally.
Supersedes: NONE

---

## DR-3 — Temporary media storage strategy
Date: 2026-04-20
Status: ACCEPTED
Context: Downloaded YouTube videos and extracted audio files need temporary storage during processing. After all extraction steps (ASR, OCR) are complete, the media files must be deleted. The system runs on a single laptop — cloud storage (S3) adds unnecessary complexity for V1.
Decision: Local filesystem storage at the path specified by the TEMP_MEDIA_PATH environment variable. Files are organized by job_id in subdirectories. Cleanup is triggered after all extraction tasks for a job complete. TEMP_MEDIA_MAX_AGE_SECONDS provides a safety net for orphaned files.
Consequences: Enables simple, fast I/O for video processing on a single machine. Rules out S3-compatible storage in V1 (deferred to future multi-machine deployment). Requires sufficient local disk space for concurrent video downloads. Media files are ephemeral — the system is NOT a video hosting or storage service.
Supersedes: NONE

---

## DR-4 — LLM/AI provider choice
Date: 2026-04-20
Status: ACCEPTED
Context: The system uses LLMs to parse aligned timeline content (ASR + OCR) and extract structured data (recipes, movie lists, scripts, etc.). Two tiers of LLM capability are needed: a local model for routine extraction tasks and a cloud model for hard reasoning tasks requiring higher accuracy or longer context windows.
Decision: Two-tier LLM strategy. Tier 1 (local): Ollama running llama3.1:8b on the same laptop — used for routine extraction, classification support, and simple structuring tasks. Tier 2 (cloud): Groq API running llama-3.3-70b-versatile — used for hard reasoning tasks, complex multi-item extraction, and fallback when local model confidence is low. Escalation logic: try Ollama first, escalate to Groq when local results fail parsing or fall below confidence threshold.
Consequences: Enables cost-effective local processing for most tasks while retaining access to a more powerful model for difficult cases. Rules out OpenAI, Anthropic, and other commercial LLM providers in V1. Requires Ollama to be installed and running locally with the llama3.1:8b model pulled. Requires a valid GROQ_API_KEY for cloud escalation. Groq usage incurs API costs on their pay-as-you-go plan.
Supersedes: NONE

---

## DR-5 — OCR engine choice
Date: 2026-04-20
Status: ACCEPTED
Context: The system needs to extract on-screen text from video frames — titles, overlays, ingredient lists, graphics, captions rendered into the video itself (not subtitle tracks). The OCR engine must run locally on a CPU-only laptop with no external API dependency.
Decision: Tesseract 5 via the pytesseract Python wrapper. Video frames are sampled at a configurable rate (OCR_FRAME_SAMPLE_RATE env var), extracted using ffmpeg, and passed to Tesseract for text recognition. Adjacent duplicate text is deduplicated to avoid repeating static overlays.
Consequences: Enables local, offline OCR with no API cost. Tesseract handles Latin-script languages well out of the box. Rules out cloud OCR services (Google Vision, AWS Textract) in V1. Accuracy on stylized or low-contrast text may be limited — this is an acceptable tradeoff for V1. May require Tesseract language packs for non-English videos.
Supersedes: NONE

---

## DR-6 — ASR / transcript engine choice
Date: 2026-04-20
Status: ACCEPTED
Context: The system needs to transcribe spoken content from YouTube videos with word-level timestamps. The ASR engine must run locally on a CPU-only laptop with no external API dependency. Accuracy must be sufficient for downstream LLM structuring — the transcript does not need to be publishing-quality, but must be good enough for entity extraction.
Decision: faster-whisper with model=small and device=cpu. This is a confirmed decision. faster-whisper is a CTranslate2-optimized implementation of OpenAI Whisper, providing significantly faster CPU inference than the original Whisper. The small model balances accuracy and CPU performance. Word-level timestamps are extracted for provenance tracking.
Consequences: Enables local, offline ASR with no API cost. CPU inference with model=small is viable on a modern laptop (expected ~2-4x slower than real-time). Rules out cloud ASR services (Google STT, AWS Transcribe, AssemblyAI) in V1. Rules out larger Whisper models (medium, large) due to CPU performance constraints. Accuracy on heavily accented or multi-speaker audio may be limited.
Supersedes: NONE

---

## DR-7 — Authentication mechanism
Date: 2026-04-20
Status: SUPERSEDED by DR-7-REV
Context: The output API must be protected to prevent unauthorized access to job submission and result retrieval. The auth mechanism must be stateless (no server-side session storage), simple to implement, and suitable for both developer API usage and frontend UI authentication.
Decision: JWT (JSON Web Tokens) with HS256 signing. Protected endpoints: POST /api/v1/jobs, GET /api/v1/jobs/{job_id}, GET /api/v1/jobs/{job_id}/result. Unprotected endpoints: GET /api/v1/health, GET /docs, GET /openapi.json, static frontend assets. JWT secret is stored in JWT_SECRET_KEY env var. Token expiry is configurable via JWT_EXPIRY_MINUTES. No refresh token mechanism in V1.
Consequences: Enables stateless authentication suitable for API and UI consumers. Rules out OAuth2 flows (deferred to future version if third-party integrations are needed). Rules out API key authentication (less flexible than JWT). No user registration or login flow is defined in V1 — token generation mechanism is left to Phase 2 implementation (could be a simple admin-generated token or a basic login endpoint).
Supersedes: NONE

## DR-7-REV — Authentication mechanism (revised)
Date: 2026-04-20
Status: ACCEPTED
Context: The output API must be protected. Building custom user registration and login flows is unnecessary when Supabase provides a fully managed authentication service that issues standard JWTs.
Decision: Phase 3 will validate Supabase-issued JWTs using the Supabase JWT secret. We are not building custom token generation, user registration, or login endpoints. The FastAPI auth dependency reads the JWT secret from the JWT_SECRET_KEY environment variable — which will be the Supabase JWT secret from the dashboard, not a custom-generated one.
Consequences: Simplifies the backend by removing user management. The python-jose library is still used. Nothing in pyproject.toml changes. Our API will trust tokens signed by Supabase.
Supersedes: DR-7

---

## DR-8 — Schema validation approach
Date: 2026-04-20
Status: ACCEPTED
Context: The system needs robust runtime validation for API request/response payloads, database models, LLM output parsing, and structured extraction schemas. The validation library must integrate naturally with the chosen API framework (FastAPI) and support JSON Schema generation for API documentation.
Decision: Pydantic v2 for all schema validation. Request models validate incoming API payloads. Response models define the structured JSON output schema. Internal models validate LLM output parsing results. Pydantic's JSON Schema generation powers the OpenAPI documentation. Strict mode is used where applicable to catch type coercion issues.
Consequences: Enables type-safe validation across the entire pipeline with minimal boilerplate. FastAPI's native Pydantic integration means request/response validation is automatic. Rules out JSON Schema (manual, no Python type integration), Protobuf (unnecessary complexity for a REST API), and marshmallow (redundant with Pydantic + FastAPI).
Supersedes: NONE

---

## DR-9 — Search and retrieval layer
Date: 2026-04-20
Status: ACCEPTED
Context: The system needs to support searching across extracted content — finding specific segments, items, or timestamps within processed videos. A dedicated search layer enables future features like cross-video search and semantic similarity queries. The V1 deployment is single-machine, so a separate search cluster (OpenSearch/Elasticsearch) adds significant resource overhead.
Decision: pgvector extension within PostgreSQL for V1. Vector embeddings are stored alongside extracted content in PostgreSQL. GIN indexes support full-text search on transcript and OCR text. Semantic similarity search uses pgvector's cosine distance operator. No separate OpenSearch or Elasticsearch cluster in V1. SCOPE REVIEW: OpenSearch may be added in a future version for cross-video search at scale, but is deferred from V1 to keep the single-machine footprint minimal.
Consequences: Enables both full-text and vector similarity search within the existing PostgreSQL database. No additional service to manage or monitor. Rules out OpenSearch/Elasticsearch in V1 (deferred). Search performance is bounded by PostgreSQL capabilities — acceptable for V1 single-user/small-team usage. Embedding generation requires a model (could use Ollama or a lightweight sentence-transformer — to be decided in Phase 7).
Supersedes: NONE

---

## DR-10 — Task queue and worker system choice
Date: 2026-04-20
Status: ACCEPTED
Context: This decision elaborates on DR-2 by specifying the worker execution strategy and task orchestration model. The pipeline has multiple sequential stages (download → ASR → OCR → align → classify → LLM structure → confidence score) that must execute in order for each job, with some stages (ASR, OCR) potentially running in parallel.
Decision: Celery task chains and chords for pipeline orchestration. Sequential stages are linked via Celery chains. ASR and OCR tasks run in parallel via a Celery chord, with the temporal alignment task as the chord callback. Worker concurrency is controlled via WORKER_CONCURRENCY env var. Task time limits are enforced via CELERY_TASK_TIME_LIMIT. Failed tasks update job status and halt the pipeline for that job. No automatic retry of the full pipeline — individual task retries are configured per task.
Consequences: Enables parallel execution of ASR and OCR stages while maintaining sequential ordering for dependent stages. Celery's built-in retry, timeout, and error handling mechanisms reduce custom orchestration code. Rules out custom pipeline orchestration frameworks. Rules out fully parallel execution of all stages (some stages depend on outputs of prior stages). Pipeline monitoring is available through Celery's built-in inspection API.
Supersedes: NONE (extends DR-2 with execution strategy details)
