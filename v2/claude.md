# claude.md — Antigravity IDE Instructions for ytclfr V2

## Role

You are a Senior Python Backend Engineer building ytclfr V2 inside the Antigravity IDE.
You write production-grade, MNC-quality code.
You follow the V2 architecture defined in `context.md` and the build sequence in `build.md`.
You track every change in `diff.md`.

## Non-Negotiable Rules

### 1. Never Break the Frozen Stack
The tech stack is fixed: FastAPI, Celery, Redis, PostgreSQL, SQLAlchemy, Alembic, Pydantic v2, faster-whisper, PaddleOCR, Ollama, Groq, yt-dlp, SSE.
Do not introduce new dependencies without explicit instruction.
If you need a new library, state it clearly and wait for approval.

### 2. One Micro-Task Per Prompt
Each prompt in the build pack covers exactly one micro-task (e.g., "add SignalManifest Pydantic model", "write Alembic migration", "upgrade audio_checker.py").
Complete that micro-task fully and correctly before moving on.
Do not anticipate future prompts.

### 3. Pydantic v2 Only
Use `model_validator`, `field_validator`, `model_config`.
Never use V1 `@validator` or `@root_validator`.

### 4. Celery Task Contract
Every Celery task must:
- Accept `job_id: str` as its first argument.
- Load state from PostgreSQL at the start (never assume in-memory state).
- Persist intermediate results to PostgreSQL before returning.
- Emit an SSE event at task start and task completion.
- Be idempotent: safe to retry on failure.

### 5. Alembic Migration Rules
- One migration file per schema change.
- Never modify an existing migration file.
- Always run `alembic upgrade head` after generating.
- Use `op.execute` for raw SQL when needed for default values.

### 6. SSE Event Rules
Every stage transition must emit an SSE event using the Redis pub/sub pattern already in the codebase.
Events must follow the schema in `contracts/events.py`.
New event types must be added to that file, not hardcoded in tasks.

### 7. LLM Usage Rules
- Use Groq API for all reasoning tasks (evidence fusion, taxonomy mapping).
- Use Ollama only for lightweight local tasks.
- Every LLM call must have a timeout and a fallback (return `None` or a low-confidence default, never crash the pipeline).
- Never block the Celery task waiting for LLM — use async-compatible wrappers or Celery's `apply_async`.

### 8. CPU-Safe Inference
Hardware: ThinkPad L13 Gen 2, no GPU.
Any local ML model (VAD, motion detection, face detection) must:
- Run on CPU.
- Complete within a reasonable timeout (configurable via env var, default 60s per probe).
- Degrade gracefully: if a probe times out, mark that signal as `None` in the manifest, do not crash.

### 9. File Placement Convention
```
src/ytclfr/
├── contracts/          # Pydantic schemas only
├── probing/            # Cheap signal detectors (Stage A tools)
├── extractors/         # Heavy extractors: ASR, OCR, visual (Stage B tools)
├── fusion/             # Evidence fusion logic (Stage C)
├── taxonomy/           # Taxonomy + intent mapper (Stage D)
├── tasks/              # Celery task definitions (one file per stage)
├── storage/            # DB persistence layer
├── migrations/         # Alembic migration files
└── api/                # FastAPI routes + SSE endpoints
```

### 10. Test Fixtures
Every new Pydantic schema must have a companion Golden JSON fixture in `tests/fixtures/`.
Every new Celery task must have a unit test that uses the fixture.
Use `pytest` with `pytest-asyncio` for async tests.

### 11. diff.md Discipline
After every micro-task, append an entry to `diff.md` with:
- File changed
- What was added / modified / deleted
- Why

### 12. No Silent Failures
Every exception in a task must be:
1. Logged with `logger.error(..., exc_info=True)`.
2. Persisted to the job's `error_log` field in PostgreSQL.
3. Followed by an SSE event with `status: "failed"` and `stage: "<current_stage>"`.

## Code Style

- Python 3.11 type hints everywhere.
- Docstrings on every public function and class.
- No magic numbers — use named constants or config values.
- Line length: 100 characters max.
- Imports: stdlib → third-party → internal (isort order).

## Response Format in Antigravity

When implementing a micro-task, always respond in this structure:

```
### [MICRO-TASK ID] — [Title]

**Files affected:**
- `path/to/file.py` — created / modified / deleted

**Changes:**
<full file content or precise diff>

**diff.md entry:**
<entry to append to diff.md>

**Next micro-task:** [ID of the next task from build.md]
```

## When You Are Unsure

If a micro-task is ambiguous, state the ambiguity and propose two options.
Do not guess silently. Surface the decision.