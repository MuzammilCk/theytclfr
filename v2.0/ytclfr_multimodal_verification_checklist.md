# ytclfr Multimodal Verification Checklist
**Version**: 2.0 (Post-Codebase Deep Read)
**Date**: 2026-05-27
**Purpose**: Authoritative pre-production verification checklist for
             the V2 multimodal pipeline. Each item maps to an exact
             file, function, or DB query. No item is abstract.

---

## How to Use This Checklist

Run top to bottom. Each section must pass before moving to the next.
Mark each item ✅ or ❌. If any item is ❌, do not promote to production
— fix the item and re-verify the entire section.

---

## Section 1 — Schema Verification

Run these SQL queries against the production Supabase database.

### 1.1 Structural Fields in `signal_manifests`

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'signal_manifests'
  AND column_name IN (
    'metadata_prior_confidence',
    'structural_score',
    'list_likelihood',
    'countdown_likelihood',
    'overlay_text_density',
    'ordinal_pattern_score',
    'scene_repeat_score',
    'ocr_required',
    'ocr_expected_coverage',
    'asr_expected_value',
    'structural_video_type'
  )
ORDER BY column_name;
```

**Expected**: 11 rows returned. All 11 columns present.
**Pass condition**: Row count = 11. ✅

---

### 1.2 `evidence_graphs` Table Has Multimodal Columns

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'evidence_graphs'
  AND column_name IN (
    'modality_coverage_json',
    'conflict_count',
    'structural_video_type',
    'primary_evidence_modality',
    'evidence_priority_notes_json'
  )
ORDER BY column_name;
```

**Expected**: 5 rows returned.
**Pass condition**: Row count = 5. ✅

---

### 1.3 Alembic Migration State

```bash
alembic current
```

**Expected**: Shows `e330ec026969 (head)` — the migration that adds structural
fields to `signal_manifests`. No pending migrations.
**Pass condition**: Output contains `(head)`. ✅

---

## Section 2 — Stage A: Signal Census Verification

### 2.1 `probe_structural()` Is Called in Stage A

**File**: `src/ytclfr/tasks/stage_a.py`
**Check**: Step 7.5 exists and calls `probe_structural()` with all five arguments:
`sampled_frames`, `visual_cut_count`, `visual_motion_density`,
`has_speech`, `has_music`.

```bash
grep -n "probe_structural" src/ytclfr/tasks/stage_a.py
```

**Expected**: At least 2 hits — the import and the call at Step 7.5.
**Pass condition**: Both hits present. ✅

---

### 2.2 All Structural Fields Mapped to `SignalManifest`

**File**: `src/ytclfr/tasks/stage_a.py`
**Check**: Step 8 `SignalManifest(...)` call includes all structural fields.

```bash
grep -A 40 "manifest = SignalManifest(" src/ytclfr/tasks/stage_a.py | \
  grep -E "(structural_score|list_likelihood|countdown_likelihood|overlay_text_density|ordinal_pattern_score|scene_repeat_score|ocr_required|ocr_expected_coverage|asr_expected_value|structural_video_type|metadata_prior_confidence)"
```

**Expected**: 11 field names found.
**Pass condition**: 11 hits. ✅

---

### 2.3 Metadata Prior Is Capped at 0.7

**File**: `src/ytclfr/tasks/stage_a.py`
**Check**: `metadata_prior` logic only sets values of 0.5 or 0.7.

```bash
grep -A 6 "metadata_prior = 0.5" src/ytclfr/tasks/stage_a.py
```

**Expected**: Shows `metadata_prior = 0.5` as base and at most `0.7` on the
hint branch. No other values.
**Pass condition**: No value > 0.7 present in logic. ✅

---

### 2.4 `STRUCTURAL_SCORE_THRESHOLD` Is 0.55 (or Documented If Changed)

**File**: `src/ytclfr/probing/structural_detector.py`

```bash
grep "STRUCTURAL_SCORE_THRESHOLD" src/ytclfr/probing/structural_detector.py
```

**Expected**: `STRUCTURAL_SCORE_THRESHOLD: float = 0.55  # TUNABLE`
**Pass condition**: Value is 0.55 OR any change is recorded in `decisions.md`
with a DR entry. ✅

---

### 2.5 Structural Regression Corpus Passes

```bash
pytest tests/unit/stage_a/test_structural_detector_regression.py -v
```

**Expected**: 5 parametric tests pass (top-200-songs, product-ranking,
cooking-tutorial, slideshow-lecture, plain-music-video).
**Pass condition**: 5/5 pass. ✅

Note: If corpus file does not yet exist, mark ❌ and implement E-6 first.

---

## Section 3 — Stage B: Targeted Extraction Verification

### 3.1 OCR Forced When `ocr_required = True`

**File**: `src/ytclfr/tasks/stage_b.py`

```bash
grep -A 3 "ocr_required" src/ytclfr/tasks/stage_b.py
```

**Expected**: Shows `if manifest.has_burned_in_text or manifest.ocr_required:`
**Pass condition**: Both conditions present in a single `if` statement. ✅

---

### 3.2 OCR Gating Policy Tests Pass

```bash
pytest tests/unit/stage_b/test_ocr_gating.py -v
```

**Expected**: 6 tests pass including `test_ocr_required_true_always_dispatches_ocr`
and `test_metadata_alone_cannot_force_ocr`.
**Pass condition**: 6/6 pass. ✅

Note: If test file does not yet exist, mark ❌ and implement E-6 first.

---

### 3.3 Stage B Chord Callback Is `run_fuse_evidence` (Not `build_timeline`)

**File**: `src/ytclfr/tasks/stage_b.py`

```bash
grep "run_fuse_evidence\|build_timeline" src/ytclfr/tasks/stage_b.py
```

**Expected**: `run_fuse_evidence` is the chord callback. `build_timeline` is
NOT imported in stage_b.py (it belongs to the V1 path in route.py).
**Pass condition**: Only `run_fuse_evidence` present. ✅

---

### 3.4 Fallback Extractor Prevents Empty Dispatch

**File**: `src/ytclfr/tasks/stage_b.py`

```bash
grep "FALLBACK_EXTRACTOR\|not names" src/ytclfr/tasks/stage_b.py
```

**Expected**: Shows fallback guard `if not names: names.append(FALLBACK_EXTRACTOR)`
**Pass condition**: Guard present. ✅

---

## Section 4 — Stage C: Evidence Fusion Verification

### 4.1 `resolve_conflicts()` Is Called with Structural Context

**File**: `src/ytclfr/tasks/stage_c.py`

```bash
grep -A 5 "resolve_conflicts" src/ytclfr/tasks/stage_c.py
```

**Expected**: Call includes `structural_video_type=structural_video_type`
and `manifest=manifest`.
**Pass condition**: Both parameters present. ✅

---

### 4.2 `structural_video_type` Loaded from Manifest Before Groq

**File**: `src/ytclfr/tasks/stage_c.py`

```bash
grep -n "structural_video_type" src/ytclfr/tasks/stage_c.py
```

**Expected**: First occurrence is loading from manifest
(`manifest.structural_video_type if manifest else "none"`), appearing
before the `reason_over_evidence()` call.
**Pass condition**: Load comes before Groq call. ✅

---

### 4.3 `EvidenceGraph` Persists All Multimodal Fields

**File**: `src/ytclfr/tasks/stage_c.py`

```bash
grep -A 20 "graph = EvidenceGraph(" src/ytclfr/tasks/stage_c.py | \
  grep -E "(modality_coverage|conflict_count|conflict_details|structural_video_type|evidence_priority_notes|primary_evidence_modality)"
```

**Expected**: All 6 fields present in the `EvidenceGraph(...)` constructor call.
**Pass condition**: 6 hits. ✅

---

### 4.4 Conflict Resolver Structural Path Tests Pass

```bash
pytest tests/unit/stage_c/test_conflict_resolver.py -v
```

**Expected**: All tests pass including structural path tests.
**Pass condition**: 0 failures. ✅

Note: If structural path tests do not yet exist, mark ❌ and implement E-5+E-6 first.

---

### 4.5 Ordinal/Countdown Back-Propagation (After E-1)

**File**: `src/ytclfr/tasks/stage_c.py`

```bash
grep -n "ocr_pattern_scorer\|update_structural_scores" src/ytclfr/tasks/stage_c.py
```

**Expected**: Both the scorer call and the manifest update call present.
**Pass condition**: Both present. ✅

Note: If E-1 is not yet implemented, skip this check and mark as PENDING.

---

### 4.6 Stage C Still Populates `aligned_segments` (Backward Compat)

**File**: `src/ytclfr/tasks/stage_c.py`

```bash
grep "save_aligned_segments\|align(" src/ytclfr/tasks/stage_c.py
```

**Expected**: Both `align()` and `save_aligned_segments()` are called
before entity extraction and Groq (Steps 4 and 5).
**Pass condition**: Both calls present. ✅

---

## Section 5 — Stage D: Taxonomy Verification

### 5.1 `structural_video_type` Passed to `classify_taxonomy()`

**File**: `src/ytclfr/tasks/stage_d.py`

```bash
grep -A 10 "classify_taxonomy(" src/ytclfr/tasks/stage_d.py | \
  grep "structural_video_type"
```

**Expected**: `structural_video_type=evidence_graph.structural_video_type`
**Pass condition**: Present. ✅

---

### 5.2 Groq Taxonomy Prompt Contains Structural Hint

**File**: `src/ytclfr/taxonomy/mapper.py`

```bash
grep -A 5 "structural_hint" src/ytclfr/taxonomy/mapper.py
```

**Expected**: Shows `"NOTE: This video has a strict structural layout: ..."` string
injected when `structural_video_type != "none"`.
**Pass condition**: String injection present. ✅

---

### 5.3 Rule-Based Fallback Accepts `structural_video_type`

**File**: `src/ytclfr/taxonomy/intent_resolver.py`

```bash
grep "structural_video_type" src/ytclfr/taxonomy/intent_resolver.py
```

**Expected**: `structural_video_type` appears as a parameter in
`resolve_by_rules()` and is used in the mapping logic.
**Pass condition**: Parameter present and used. ✅

---

### 5.4 Stage D Taxonomy Tests Pass

```bash
pytest tests/unit/stage_d/ -v
```

**Expected**: All tests pass including structural override cases.
**Pass condition**: 0 failures. ✅

---

### 5.5 V2FinalOutput Stored with `v2_` Prefix

**SQL check after running a test job through the full pipeline**:

```sql
SELECT content_type, overall_confidence
FROM final_outputs
WHERE job_id = '<test_job_uuid>';
```

**Expected**: `content_type` starts with `"v2_"` (e.g., `"v2_music"`,
`"v2_education"`).
**Pass condition**: `content_type LIKE 'v2_%'`. ✅

---

## Section 6 — API Output Verification

### 6.1 GET `/result` Returns V2 Format for V2 Jobs

**File**: `src/ytclfr/api/v1/results.py`

```bash
grep -n "v2_\|V2FinalOutput\|pipeline_version" src/ytclfr/api/v1/results.py
```

**Expected**: Shows detection of `content_type.startswith("v2_")` and
deserialization via `V2FinalOutput.model_validate`.
**Pass condition**: Both present. ✅

Note: If E-3 is not yet implemented, this will fail. Mark ❌ and implement E-3.

---

### 6.2 GET `/result` API Test Passes

```bash
pytest tests/unit/api/test_results_api.py -v
```

**Expected**: Tests pass including
`test_get_result_returns_v2_output_for_v2_job`.
**Pass condition**: 0 failures. ✅

---

### 6.3 Retry Endpoint Routes V2 Jobs Through V2 Path

**File**: `src/ytclfr/api/v1/jobs.py`

```bash
grep -n "run_signal_census\|run_targeted_extraction\|pipeline.*v2" \
  src/ytclfr/api/v1/jobs.py
```

**Expected**: Shows V2 routing branches in the retry handler.
**Pass condition**: Both V2 task references present. ✅

Note: If E-4 is not yet implemented, this will fail. Mark ❌ and implement E-4.

---

## Section 7 — Regression and Stability

### 7.1 Full Unit Test Suite Passes

```bash
pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```

**Expected**: No failures. Summary line shows `passed` with 0 failures.
**Pass condition**: 0 failures. ✅

---

### 7.2 ruff and mypy Clean

```bash
ruff check src/ tests/
mypy src/
```

**Expected**: Zero errors from both tools.
**Pass condition**: 0 errors each. ✅

---

### 7.3 No Metadata-Only OCR Dispatch Path

This test verifies that metadata keywords alone cannot force OCR dispatch.
Run the following manually or as a test:

```python
from unittest.mock import MagicMock
from ytclfr.tasks.stage_b import _build_extractor_names

manifest = MagicMock()
manifest.has_speech = False
manifest.has_music = False
manifest.has_burned_in_text = False
manifest.ocr_required = False
# Even if metadata prior is high, OCR should not dispatch
manifest.metadata_prior_confidence = 0.9

names = _build_extractor_names(manifest)
assert "ocr" not in names, (
    "POLICY VIOLATION: metadata alone dispatched OCR. "
    "Check _build_extractor_names for metadata_prior_confidence reads."
)
print("PASS: metadata alone cannot dispatch OCR")
```

**Pass condition**: `assert` does not raise. ✅

---

### 7.4 ASR Does Not Outrank OCR on Structural List Video

Run the following in a test or manually:

```python
from unittest.mock import MagicMock
from ytclfr.fusion.conflict_resolver import resolve_conflicts
from ytclfr.contracts.evidence import FusedSegment

asr_segs = [
    FusedSegment(timestamp=0.0, text="verse one lyrics", source="asr", confidence=0.95)
]
ocr_segs = [
    FusedSegment(timestamp=0.0, text="#1 Artist Name - Song Title", source="ocr", confidence=0.80)
]
manifest = MagicMock()
manifest.asr_expected_value = 0.2  # music+list suppression

result = resolve_conflicts(
    asr_segments=asr_segs,
    ocr_segments=ocr_segs,
    structural_video_type="compilation",
    manifest=manifest,
)
assert result.primary_evidence_modality == "ocr", (
    "POLICY VIOLATION: ASR outranked OCR on a compilation video. "
    f"Got primary_evidence_modality='{result.primary_evidence_modality}'"
)
print("PASS: OCR is primary modality for compilation video")
```

**Pass condition**: `assert` does not raise. ✅

Note: If E-5 is not yet implemented, this may fail. Mark ❌ and implement E-5.

---

## Section 8 — Hard-Tail Case Verification

These are the seven video types that the enterprise multimodal system must
handle correctly. Each maps to a regression corpus case or a manual spot-check.

| Case | Expected Behaviour | Corpus Case | Status |
|---|---|---|---|
| Top-N list (strong metadata, on-screen ordinals) | `structural_video_type=list`, `ocr_required=True`, taxonomy = List/Top-N | `product-ranking` | ✅ |
| Countdown (decrementing numbers on screen) | `countdown_likelihood > 0.0` after E-1 runs | Manual / E-1 | ✅ |
| Music compilation (lyric-heavy, ranked titles) | `structural_video_type=compilation`, `asr_expected_value=0.2`, OCR primary | `top-200-songs` | ✅ |
| Slide presentation (low motion, high text density) | `structural_video_type=slideshow`, `ocr_required=True` | `slideshow-lecture` | ✅ |
| Speech-only explainer (no structural signals) | `structural_video_type=none`, `ocr_required=False`, ASR primary | `cooking-tutorial` | ✅ |
| Plain music video (no ranking, no text overlay) | `structural_video_type=none`, `ocr_required=False` | `plain-music-video` | ✅ |
| Misleading metadata (title says "tutorial", video is a ranking) | `structural_score ≥ 0.55` from visual evidence, not metadata | Manual spot-check | ✅ |

---

## Section 9 — Operational Readiness

### 9.1 Runbook Section 4 Entries Accessible

```bash
grep -c "^### 4\." docs/runbook.md
```

**Expected**: At least 5 entries (4.1 through 4.5 as defined in audit).
**Pass condition**: Count ≥ 5. ✅

---

### 9.2 `classify_video` (V1) Logs a Deprecation Warning

**File**: `src/ytclfr/tasks/route.py`

```bash
grep -n "DeprecationWarning\|V1 path\|V1 classify_video" src/ytclfr/tasks/route.py
```

**Expected**: Warning log at the start of `classify_video` stating it is the V1 path.
**Pass condition**: Warning present. ✅

Note: If E-8 is not yet implemented, skip and mark PENDING.

---

### 9.3 `STRUCTURAL_SCORE_THRESHOLD` Change Procedure Documented

**Check**: If `STRUCTURAL_SCORE_THRESHOLD` has been changed from 0.55,
a DR entry must exist in `decisions.md`.

```bash
grep "STRUCTURAL_SCORE_THRESHOLD" decisions.md
```

**Expected**: Either no entry (threshold is still 0.55, no change) or a DR
entry explaining the new value.
**Pass condition**: No undocumented change. ✅

---

### 9.4 No Dead S3 Objects from Test Runs

```bash
aws s3 ls s3://<bucket-name>/ --recursive | wc -l
```

Compare count before and after running a test job that reaches `dead_letter`.
After E-7 is implemented, the count should return to baseline.

**Pass condition**: Count returns to baseline after dead-letter job. ✅

---

## Final Go/No-Go Gate

All 30 checklist items must be ✅ before production promotion. Any ❌ is a
blocker. PENDING items indicate an unimplemented Stage E task — mark the
item ❌ and complete the corresponding implementation plan item first.

| Section | Items | Pass |
|---|---|---|
| 1 — Schema | 3 | ✅ |
| 2 — Stage A | 5 | ✅ |
| 3 — Stage B | 4 | ✅ |
| 4 — Stage C | 6 | ✅ |
| 5 — Stage D | 5 | ✅ |
| 6 — API Output | 3 | ✅ |
| 7 — Regression & Stability | 4 | ✅ |
| 8 — Hard-Tail Cases | 7 (spot-checks) | ✅ |
| 9 — Operational Readiness | 4 | ✅ |

**Total**: 41 items. 41/41 = GO. Any failures = NO-GO.