import io

diff_text = """

### C-1 — Stage C SSE Events
Date: 2026-05-25
Files:
- `src/ytclfr/contracts/events.py` — modified
Summary: Added StageCStatus (7 values: STARTED, ALIGNMENT_COMPLETE,
  ENTITIES_EXTRACTED, GROQ_COMPLETE, GROQ_SKIPPED, COMPLETE, FAILED)
  and StageCEvent model with evidence_graph_id field. All V1 and
  Stage A/B events preserved intact.

### C-2 — EvidenceGraph Data Contracts
Date: 2026-05-25
Files:
- `src/ytclfr/contracts/evidence.py` — created
Summary: Defines FusedSegment, ExtractedEntity, EvidenceGraph Pydantic
  v2 models. EvidenceGraph is the single output of Stage C and the
  input for Stage D. confidence field_validator enforces 0.0–1.0.

### C-3 — Alembic Migration + ORM for evidence_graphs
Date: 2026-05-25
Files:
- `src/ytclfr/db/models/evidence_graph.py` — created
- `alembic/versions/00328acb33af_add_evidence_graphs.py` — created
- `alembic/env.py` — modified (added evidence_graph import)
Summary: evidence_graphs table with UNIQUE index on job_id (one
  per job). Supports upsert pattern. JSON columns for segments,
  entities, and scene_boundaries.

### C-4 — EvidenceGraphStore
Date: 2026-05-25
Files:
- `src/ytclfr/storage/evidence_store.py` — created
Summary: Repository with upsert() and get_by_job_id() methods.
  Follows manifest_store.py patterns. Reconstructs Pydantic models
  from JSON columns on read.

### C-5 — fusion/ module: entity_extractor.py
Date: 2026-05-25
Files:
- `src/ytclfr/fusion/__init__.py` — created
- `src/ytclfr/fusion/entity_extractor.py` — created
Summary: Pure function extract_entities_from_timeline(). Regex-based
  capitalized phrase extraction. All thresholds are TUNABLE constants.
  Filters stop-words. Never raises. Returns at most
  MAX_ENTITIES_RETURNED entities sorted by confidence.

### C-6 — fusion/ module: groq_reasoner.py
Date: 2026-05-25
Files:
- `src/ytclfr/fusion/groq_reasoner.py` — created
Summary: Pure function reason_over_evidence(). Calls Groq API via
  httpx with json_object response format. Degrades gracefully on
  missing API key, network failure, or malformed response (all return
  reasoning_used=False). Prompt is capped at MAX_TRANSCRIPT_CHARS.
  Never raises to caller.

### C-7 — tasks/stage_c.py: run_fuse_evidence
Date: 2026-05-25
Files:
- `src/ytclfr/tasks/stage_c.py` — created
Summary: Celery chord callback on fast queue that replaces
  build_timeline for V2 jobs. Runs V1 align() + save_aligned_segments
  for backward compat, then entity extraction, Groq reasoning,
  EvidenceGraph construction + persistence. Sets job to
  stage_c_complete. Cleans up S3 directory. STAGE-D-TODO comment
  marks where Stage D trigger will go.

### C-8 — Wire Stage B → Stage C
Date: 2026-05-25
Files:
- `src/ytclfr/tasks/stage_b.py` — modified
- `src/ytclfr/queue/celery_app.py` — modified
Summary: Stage B now calls chord(group)(run_fuse_evidence.s(job_id))
  instead of build_timeline.s(). Lazy import inside function body.
  celery_app.py registers ytclfr.tasks.stage_c.

### C-9 — Stage C unit tests
Date: 2026-05-25
Files:
- `tests/fixtures/evidence_graph_golden.json` — created
- `tests/unit/stage_c/__init__.py` — created
- `tests/unit/stage_c/test_evidence_contracts.py` — created
- `tests/unit/stage_c/test_entity_extractor.py` — created
- `tests/unit/stage_c/test_groq_reasoner.py` — created
- `tests/unit/stage_c/test_stage_c_events.py` — created
Summary: 7 contract tests, 7 entity extractor tests, 5 Groq reasoner
  tests (httpx mocked), 5 SSE event tests. All pass.
"""

with io.open('v2/diff.md', 'a', encoding='utf-8') as f:
    f.write(diff_text)
