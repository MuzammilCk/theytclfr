# ytclfr — Project Context (V2)

## What This Project Is

**ytclfr** (YouTube Content Lifter and Field Recognizer) is an AI-powered video intelligence pipeline.
Given a YouTube URL, it downloads the video, analyzes its content using multiple AI/ML extractors, and produces a structured JSON output describing the video's category, intent, extracted items, and timeline.

## Tech Stack (Frozen — Do Not Change)

| Layer | Technology |
|---|---|
| API server | FastAPI |
| Task queue | Celery |
| Message broker | Redis |
| Database | PostgreSQL |
| ORM / migrations | SQLAlchemy + Alembic |
| Video download | yt-dlp |
| Speech recognition | faster-whisper (ASR) |
| OCR | PaddleOCR |
| AI / LLM (local) | Ollama |
| AI / LLM (cloud) | Groq API |
| Schema validation | Pydantic v2 |
| Streaming | SSE (Server-Sent Events via Redis pub/sub) |
| Runtime | Python 3.11 |

## Hardware Constraint

ThinkPad L13 Gen 2 — no dedicated GPU. All local inference must be CPU-safe.
Groq API is the preferred LLM for complex reasoning tasks.
Ollama handles routine/cheap LLM calls locally.

## Current Codebase Structure (V1)

```
src/ytclfr/
├── api/                    # FastAPI routes
├── config.py               # Ollama + Groq config, env vars
├── contracts/
│   ├── events.py           # SSE event schemas
│   ├── router.py           # RouterDecisionModel (V1 — to be replaced)
│   └── output.py           # FinalOutputModel
├── router/
│   └── classifier.py       # Heuristic-based early guesser (V1 — to be replaced)
├── tasks/
│   ├── route.py            # Celery entry task, fires group(ASR, OCR, audio)
│   ├── asr.py              # faster-whisper task
│   ├── ocr.py              # PaddleOCR task
│   ├── audio_classifier.py # Audio metadata task
│   └── align.py            # Basic interval merge (V1 — to be elevated)
├── alignment/
│   └── engine.py           # Low-level timestamp math
├── probing/
│   ├── audio_checker.py    # Audio metadata probe (V1 — upgrade target)
│   └── frame_sampler.py    # Frame extraction (V1 — upgrade target)
└── storage/
    └── output_store.py     # Persists FinalOutput, hardcoded content_type_map
```

## V1 Architecture Problem (Root Cause)

V1 makes a **premature commitment**. The router reads cheap metadata (title keywords, audio bitrate) and forces the video into a hard label (`RouterDecision`) **before any content has been analyzed**. Then it blindly fires ALL extractors — ASR + OCR + audio classifier — for every video, regardless of whether those extractors are needed. This wastes CPU and produces unreliable output because the final `content_type` is anchored to the early guess, not the actual evidence.

## V2 Philosophy

**Evidence-Based Late Binding.**

Do not guess the video type first. First detect what signals are physically present. Then run only the extractors that match those signals. Then fuse all evidence. Then classify last.

This mirrors how Google Cloud Video Intelligence and Azure AI Video Indexer operate internally: separate specialized feature detectors, then a reasoning layer on top.

## V2 Pipeline — Four Stages

```
URL
 → Ingestion (unchanged)
 → Stage A: Signal Census         ← detect what signals exist
 → Stage B: Targeted Extraction   ← run only needed extractors
 → Stage C: Evidence Fusion       ← combine into one fused timeline
 → Stage D: Taxonomy + Intent     ← classify last, backed by evidence
 → Final Output + Persistence
```

### Stage A — Signal Census
Probes the raw video/audio file cheaply and produces a `SignalManifest`:
- Audio type (speech / music / both / SFX / ambient / silent)
- Language detected
- Motion density (cuts per minute, motion score)
- Face/person presence
- Burned-in text / subtitle track availability
- Aspect ratio / format (landscape, vertical, square)
- Live action / animation / screen recording
- Scene cut count

### Stage B — Targeted Extraction
Reads the `SignalManifest` and builds a **dynamic Celery group** — only fires extractors that are needed:
- `has_speech` → run ASR
- `has_burned_in_text` → run OCR
- `has_complex_visuals` → run visual extractor
- `has_music` → run audio event detector

### Stage C — Evidence Fusion
Takes all extractor outputs and builds a unified evidence graph:
- Aligned transcript + OCR + scene boundaries
- Extracted entities (products, people, places)
- Confidence scores per segment
- Timestamps and provenance

### Stage D — Taxonomy + Intent Mapping
LLM-driven final classification over the evidence graph:
- Parent category (Education, Shopping, Sports, Music, Film…)
- Child category (Tutorial, Product Review, Highlights…)
- Intent (must watch, walkthrough, comparison…)
- Evidence provenance linking classification back to timestamps

## Key V2 Contracts

### SignalManifest (replaces RouterDecisionModel)
```python
class SignalManifest(BaseModel):
    job_id: UUID
    audio_type: Literal["speech_only","music_only","speech_music","sfx","ambient","silent"]
    language: str | None
    has_speech: bool
    has_music: bool
    has_burned_in_text: bool
    has_subtitle_track: bool
    has_faces: bool
    motion_density: float        # cuts per minute
    motion_score: float          # 0.0–1.0
    aspect_ratio: str            # "16:9", "9:16", "1:1"
    content_format: Literal["live_action","animation","screen_recording","mixed"]
    scene_cut_count: int
    duration_seconds: float
    probing_confidence: float
    created_at: datetime
```

### FinalOutput (enriched)
```python
class FinalOutput(BaseModel):
    job_id: UUID
    taxonomy: dict               # {parent, child, intent}
    summary: str
    items: list[ExtractedItem]   # products, recipes, listicles…
    evidence_graph: list[dict]   # fused timeline with timestamps
    provenance: dict             # links taxonomy claims → seconds
    confidence: dict             # field-level confidence scores
    fallback_notes: list[str]
```

## Environment Variables (config.py — existing)

```
GROQ_API_KEY
OLLAMA_BASE_URL
REDIS_URL
DATABASE_URL
DOWNLOAD_DIR
```

## Build Discipline

- One Alembic migration per schema change. Never edit old migrations.
- Pydantic v2 model_validator and field_validator patterns only.
- All Celery tasks must be idempotent (safe to retry).
- SSE events must be emitted at the start and end of each stage.
- All heavy local inference must have a CPU fallback path.
- Each stage produces a persisted intermediate record in PostgreSQL before the next stage starts.