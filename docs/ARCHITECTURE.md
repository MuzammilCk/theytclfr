# ytclfr - System Architecture

ytclfr is a robust, distributed video intelligence pipeline designed to ingest YouTube videos and extract structured, meaningful content (spoken words, on-screen text, temporal context) and classify video intents.

## 1. High-Level Data Flow

The following diagram illustrates the lifecycle of a video processing job through the system (V1/V2 Flow).

```mermaid
flowchart TD
    User([User / API Client]) -->|POST /api/v1/jobs <br> URL| API(FastAPI REST API)
    API -->|job enqueue| RedisCache[(Redis Broker/Cache)]
    RedisCache -->|consume task| Worker[Celery Worker Pool]
    
    subgraph Worker Nodes
        Worker -->|1. Download| YTDLP[yt-dlp]
        YTDLP -->|Save Temp| TempStorage[(Local FS / S3)]
        
        Worker -->|2. Preflight| Router[Preflight Router]
        Worker -->|3. Extract Meta| Metadata[Metadata Extractor]
        
        Worker -->|4. ASR| ASR[faster-whisper]
        Worker -->|4. OCR| OCR[Tesseract OCR]
        
        ASR --> Align[Temporal Alignment Layer]
        OCR --> Align
        
        Align --> LLM[LLM Structuring]
        
        subgraph AI Models
            LLM --> LocalLLM[Ollama - llama3.1:8b]
            LLM --> CloudLLM[Groq - llama-3.3-70b]
        end
        
        LLM --> Confidence[Confidence Controller]
        Confidence --> JSONGen[Structured JSON Assembly]
    end
    
    JSONGen -->|Persist Results| DB[(PostgreSQL + pgvector)]
    DB --> API
    API -->|GET /api/v1/jobs/id/result| User
```

## 2. Core Components

### 2.1 API Layer (FastAPI)
- **Role:** Ingests URLs, returns job IDs, provides job status polling, and serves final structured JSON.
- **Auth:** Secured via JWT (JSON Web Tokens).
- **Validation:** Pydantic v2 schemas ensure strict runtime validation and automatic OpenAPI documentation generation.

### 2.2 Task Queue & Workers (Celery & Redis)
- **Role:** Handles asynchronous processing of long-running video extraction tasks.
- **Topology:** Designed for heterogeneous distributed deployment (e.g., separate ingest workers, heavy ML workers for ASR/OCR, fast workers for quick metadata).
- **Broker/Backend:** Redis 7 acts as both the Celery message broker and a fast cache for temporary states.

### 2.3 Storage Layer
- **Relational DB:** PostgreSQL 16 (hosted via Supabase) persists job states, metadata, and final structured output.
- **Vector DB:** `pgvector` extension is used natively within Postgres for semantic/vector similarity search using GIN indexes.
- **Temporary Object Storage:** AWS S3 (via `boto3`) is used for distributed media transport between worker nodes. Local filesystems are strictly used for transient scratch storage during task execution.

## 3. Extraction Engines

The pipeline utilizes multiple specialized engines for data extraction:
- **ASR (Speech-to-Text):** `faster-whisper` (model: small, compute: int8, device: cpu) for word-level timestamps.
- **OCR (On-Screen Text):** `Tesseract 5` via `pytesseract` for frame-level text extraction.
- **LLM Structuring (Local):** `Ollama` running `llama3.1:8b` for routine structuring and extraction.
- **LLM Reasoning (Cloud):** `Groq` API running `llama-3.3-70b-versatile` for complex reasoning and taxonomy classification tasks.
- **Embeddings:** `nomic-embed-text` via Ollama for generating vector representations stored in pgvector.

## 4. Pipeline Evolution: V1 → V2 → V3

### V1 Philosophy
In V1, videos undergo a preemptive routing classification, followed by parallel execution of all extractors (ASR, OCR). The results are then combined.

### V2 Philosophy (Evidence-Based Late Binding)
V2 introduces a more efficient, four-stage pipeline designed to prevent premature commitment to expensive extractions:
1. **Stage A (Signal Census):** Cheap physical signal detection (Voice Activity Detection, scene cuts, motion density, metadata). Produces a `SignalManifest`.
2. **Stage B (Targeted Extraction):** Dynamically invokes only the heavy extractors (e.g., OCR, ASR) that are necessary based on the `SignalManifest` from Stage A.
3. **Stage C (Evidence Fusion):** Temporal alignment, entity extraction, and reasoning over the extracted signals using Groq. Introduces conflict resolution logic where inferred structure dictates confidence (e.g., OCR is prioritized for structured layouts, ASR for speech-heavy formats).
4. **Stage D (Taxonomy + Intent):** Final video classification backed by the complete evidence graph. Employs late-binding of structural context where inferred layout (list, ranking) overrides static metadata as a hard structural prior.

## 5. V3 Architecture (Current)

V3 builds upon V2's four-stage pipeline but introduces strict contract isolation (`frozen=True` models), explicit ASR degradation detection, and resource views for the API.

```mermaid
flowchart TD
    User([User / API Client]) -->|POST /api/v3/jobs <br> URL| API(FastAPI REST API)
    API -->|job enqueue| RedisCache[(Redis Broker/Cache)]
    RedisCache -->|consume task| Ingest[Ingestion Worker]
    
    Ingest -->|Upload MP4| S3[(AWS S3)]
    Ingest -->|Trigger| StageA[Stage A: Signal Census]
    
    StageA -->|Probe Audio/Visual| S3
    StageA -->|Create| Manifest[SignalManifest]
    Manifest --> StageB[Stage B: Targeted Extraction]
    
    StageB -->|Dynamic Dispatch| Extractors(ASR / OCR)
    Extractors -->|Download MP4| S3
    Extractors -->|Produce| Bundle[ExtractorBundle + ASRMetrics]
    
    Bundle --> StageC[Stage C: Evidence Fusion]
    StageC -->|Conflict Resolution| Resolved[Aligned Segments]
    Resolved -->|Structured Prompt| Groq[Groq LLM]
    Groq --> EvidenceGraph[EvidenceGraph]
    
    EvidenceGraph --> StageD[Stage D: Taxonomy + Intent]
    StageD --> FinalResponse[FinalResponse JSON]
    FinalResponse --> DB[(PostgreSQL)]
    
    User -->|GET /api/v3/results/id?view=FULL| API
    API --> DB
```
