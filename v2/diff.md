# diff.md — ytclfr V2 Change Log

## V2 Control File Set

Files live in `V2/`. The Stage A prompt (Part C) creates `decisions.md` as the fifth file.

| File | Status |
|---|---|
| `V2/context.md` | Created — project context and frozen stack |
| `V2/claude.md` | Created — AI behavioral rules |
| `V2/build.md` | Created — stage plan and checklists |
| `V2/diff.md` | Created — this file |
| `V2/decisions.md` | **Created in Stage A Part C** — DR-V2-01, 02, 03 |

```
### [TASK-ID] — [Title]
**Date:** YYYY-MM-DD
**Files:**
- `path/to/file.py` — [created | modified | deleted]
**Summary:** One sentence describing what changed and why.
```

Keep entries in chronological order. Never edit a past entry.

---

## V1 → V2 Architectural Summary

| Component | V1 | V2 | Status |
|---|---|---|---|
| `contracts/router.py` | `RouterDecisionModel` — single early label | DEPRECATED | Pending deletion after A-1 |
| `contracts/manifest.py` | Does not exist | `SignalManifest` — multi-signal evidence object | Pending A-1 |
| `router/classifier.py` | Heuristic keyword guesser | DEPRECATED | Pending deletion after A-7 |
| `tasks/route.py` | Fires all extractors blindly | Gutted: only triggers Stage A | Pending W-1 |
| `tasks/stage_a.py` | Does not exist | Signal Census orchestrator | Pending A-7 |
| `tasks/stage_b.py` | Does not exist | Dynamic extraction group builder | Pending B-6 |
| `tasks/stage_c.py` | Does not exist | Evidence fusion + Groq reasoner | Pending C-6 |
| `tasks/stage_d.py` | Does not exist | Taxonomy + intent mapper | Pending D-5 |
| `tasks/align.py` | Basic interval merge | Merged into Stage C fusion | Pending C-6 |
| `probing/audio_checker.py` | Reads codec metadata only | VAD + music detection | Pending A-4 |
| `probing/frame_sampler.py` | Pulls 5 static frames | Motion score + face + text density | Pending A-5 |
| `probing/metadata_probe.py` | Does not exist | yt-dlp metadata + subtitle track parser | Pending A-6 |
| `storage/output_store.py` | Hardcoded `content_type_map` | Removed map, accepts rich `FinalOutput` | Pending D-6 |
| `contracts/output.py` | `content_type: str` field | Full taxonomy + evidence + provenance | Pending D-1 |
| `alignment/engine.py` | Basic timestamp math | V2 temporal alignment with confidence | Pending C-3 |
| `fusion/` directory | Does not exist | Evidence fusion layer | Pending C-4/C-5 |
| `taxonomy/` directory | Does not exist | Taxonomy + intent mapping layer | Pending D-3/D-4 |

---

## Change Entries

<!-- Append entries below this line after each micro-task -->

### A-1 — SignalManifest Pydantic Model
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/contracts/manifest.py` — created
**Summary:** Pure Pydantic v2 data contract for Stage A output. Validators enforce probing_confidence (0–1), motion_score (0–1), duration_seconds (≥0). No DB/Celery/API imports.

### A-2 — Alembic Migration: signal_manifests table
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/db/models/signal_manifest.py` — created
- `src/ytclfr/db/models/__init__.py` — modified (added SignalManifestORM)
- `alembic/env.py` — modified (added signal_manifest import)
- `alembic/versions/6c08e88f31be_add_signal_manifests.py` — created
**Summary:** ORM model and migration for signal_manifests table with FK to jobs. Cleaned autogenerate output to remove spurious drops of existing V1 indexes. Migration applied successfully.

### A-3 — SignalManifestStore
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/storage/manifest_store.py` — created
**Summary:** Repository class with create, get_by_job_id, and update_confidence methods. Follows existing storage patterns.

### A-4 — Audio Checker (VAD + Music Detection)
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/probing/__init__.py` — created
- `src/ytclfr/probing/audio_checker.py` — created
**Summary:** Full audio probe with webrtcvad VAD, librosa music detection, ffprobe metadata. Windows-compatible threading timeout (DR-V2-03). All thresholds are TUNABLE constants. Never raises.

### A-5 — Frame Sampler (Visual Probe)
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/probing/frame_sampler.py` — created
**Summary:** Visual probe with OpenCV: motion scoring, scene cut detection, Haar cascade face detection, burned-in text heuristic, content format classification. Threading timeout. Never raises.

### A-6 — Metadata Probe
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/probing/metadata_probe.py` — created
**Summary:** Parses yt-dlp .info.json for duration, aspect ratio, subtitles, chapters, tags. Zero ML, zero subprocesses. Raises FileNotFoundError/ValueError; caller handles.

### A-7 — Stage A Celery Task
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/tasks/stage_a.py` — created
**Summary:** Orchestrating task: probes metadata/audio/visual, merges into SignalManifest, persists via store. SSE events at each step via Redis pub/sub. Idempotent. Max 2 retries. STAGE-B-TODO for downstream trigger.

### A-8 — Stage A SSE Events
**Date:** 2026-05-23
**Files:**
- `src/ytclfr/contracts/events.py` — modified
**Summary:** Added StageAStatus enum (6 statuses) and StageAEvent Pydantic model. All V1 event types preserved. Added Field import.

### A-9 — Golden Fixture + Unit Tests
**Date:** 2026-05-23
**Files:**
- `tests/fixtures/signal_manifest_golden.json` — created
- `tests/unit/stage_a/__init__.py` — created
- `tests/unit/stage_a/test_contracts.py` — created
- `tests/unit/stage_a/test_metadata_probe.py` — created
- `tests/unit/stage_a/test_audio_probe.py` — created
- `tests/unit/stage_a/test_stage_a_events.py` — created
**Summary:** 27 unit tests covering SignalManifest validation, metadata probe edge cases, audio probe mocking, and SSE event contracts. All tests pass.

### V1 Baseline Note
**Date:** 2026-05-23
**Summary:** V1 tests: 209 passed, 1 skipped, 3 pre-existing integration errors in tests/integration/test_chaos.py (missing db_session fixture — not related to V2 changes). No V1 fixes needed.

### SCOPE REVIEW Notes
- **webrtcvad-wheels** — Required for VAD in audio_checker.py. Installed via `webrtcvad-wheels` (pre-built Windows wheel) since `webrtcvad` requires C compilation unavailable on system.
- **librosa** — Required for beat tracking and spectral centroid music detection in audio_checker.py.
- Both packages are explicitly required by the Stage A build plan and V2/build.md checklist.

### V2/decisions.md Created
**Date:** 2026-05-23
**Files:**
- `V2/decisions.md` — created
**Summary:** Three decision records: DR-V2-01 (Evidence-Based Late Binding), DR-V2-02 (pure function probers), DR-V2-03 (Windows threading timeout).