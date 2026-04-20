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
