# ytclfr Multimodal Implementation Plan
**Version**: 2.0 (Post-Codebase Deep Read)
**Date**: 2026-05-27
**Phase**: V2 Stage E — Multimodal Hardening
**Owner**: Next session
**Input**: 7 confirmed gaps from multimodal audit v2.0

---

## Execution Rules (MNC-Grade)

Before implementing any item:
1. Read the relevant SKILL.md if creating new files.
2. Read the file you are about to change immediately before editing.
3. Run `ruff check src/ tests/`, `mypy src/`, `pytest tests/unit/ -v` after every item.
4. All new constants go at module top, named in UPPER_CASE, with a `# TUNABLE` comment.
5. All new functions must have a docstring and `# Never raises` if that is the contract.
6. No new library dependencies without a DR entry in `decisions.md`.
7. After every item, append to `diff.md` with the date, files changed, and summary.
8. Mark the build.md checkbox for the item before moving to the next.

---

## Item E-1 — Fix `ordinal_pattern_score` Back-Propagation

**Priority**: P2
**Effort**: ~2 hours
**Blocks**: Full ordinal-based structural detection accuracy

### Context

`SignalManifest.ordinal_pattern_score` is always `0.0` because Stage A
deliberately avoids running Tesseract during probing (correct decision).
After Stage B runs full OCR, the OCR segments contain ordinal text that
could be used to update this score, but no code does this.

### Implementation

**Step 1** — Create `src/ytclfr/probing/ocr_pattern_scorer.py`

```python
"""Post-OCR ordinal and countdown pattern scoring.

Called in Stage C (after OCR segments are available) to back-populate
ordinal_pattern_score and countdown_likelihood in the SignalManifest.

Pure function — no DB, no Celery. Never raises.
"""

import re
from dataclasses import dataclass

# ── TUNABLE CONSTANTS ──────────────────────────────────────────
ORDINAL_REGEX = re.compile(
    r"(?i)\b(?:top\s*\d+|#\s*\d+|no\.?\s*\d+|\d+(?:st|nd|rd|th))\b"
)
ORDINAL_MIN_HITS_FOR_HIGH_SCORE: int = 3       # TUNABLE
ORDINAL_MAX_HITS_FULL_SCORE: int = 8           # TUNABLE
COUNTDOWN_MIN_SEQUENCE_LENGTH: int = 3         # TUNABLE
COUNTDOWN_MAX_GAP: int = 2                     # TUNABLE (allows "10, 8, 6")


@dataclass
class OcrPatternResult:
    ordinal_pattern_score: float  # 0.0–1.0
    countdown_likelihood: float   # 0.0–1.0
    ordinal_hits: int
    has_decrementing_sequence: bool


def score_ocr_patterns(ocr_segments: list[dict]) -> OcrPatternResult:
    """Scan OCR segments for ordinal and countdown patterns.

    Args:
        ocr_segments: List of OCR segment dicts with 'text' field.

    Returns:
        OcrPatternResult. Never raises.
    """
    try:
        return _score_inner(ocr_segments)
    except Exception:
        return OcrPatternResult(
            ordinal_pattern_score=0.0,
            countdown_likelihood=0.0,
            ordinal_hits=0,
            has_decrementing_sequence=False,
        )


def _score_inner(ocr_segments: list[dict]) -> OcrPatternResult:
    all_text = " ".join(
        seg.get("text", "") for seg in ocr_segments
    )
    hits = ORDINAL_REGEX.findall(all_text)
    ordinal_hits = len(hits)
    ordinal_score = min(
        ordinal_hits / ORDINAL_MAX_HITS_FULL_SCORE, 1.0
    )

    # Countdown detection: extract all standalone integers and
    # check for a monotonically decreasing sequence.
    numbers = [
        int(m) for m in re.findall(r"\b(\d+)\b", all_text)
        if 1 <= int(m) <= 200
    ]
    countdown = _detect_countdown(numbers)

    return OcrPatternResult(
        ordinal_pattern_score=round(ordinal_score, 3),
        countdown_likelihood=round(0.9 if countdown else 0.0, 3),
        ordinal_hits=ordinal_hits,
        has_decrementing_sequence=countdown,
    )


def _detect_countdown(numbers: list[int]) -> bool:
    """Return True if numbers contain a decreasing sequence
    of at least COUNTDOWN_MIN_SEQUENCE_LENGTH, allowing gaps
    of at most COUNTDOWN_MAX_GAP between values."""
    if len(numbers) < COUNTDOWN_MIN_SEQUENCE_LENGTH:
        return False
    run = 1
    for i in range(1, len(numbers)):
        diff = numbers[i - 1] - numbers[i]
        if 1 <= diff <= COUNTDOWN_MAX_GAP:
            run += 1
            if run >= COUNTDOWN_MIN_SEQUENCE_LENGTH:
                return True
        else:
            run = 1
    return False
```

**Step 2** — Add `update_structural_scores()` to `storage/manifest_store.py`

```python
def update_structural_scores(
    self,
    session: Session,
    job_id: UUID,
    ordinal_pattern_score: float,
    countdown_likelihood: float,
) -> None:
    """Partial update: back-populate ordinal and countdown scores
    after Stage B OCR results are available in Stage C.

    Never raises — update failure is logged as WARNING.
    """
    try:
        record = (
            session.query(SignalManifestModel)
            .filter(SignalManifestModel.job_id == job_id)
            .first()
        )
        if record:
            record.ordinal_pattern_score = ordinal_pattern_score
            record.countdown_likelihood = countdown_likelihood
            session.commit()
            logger.debug(
                "Updated ordinal_pattern_score=%.3f "
                "countdown_likelihood=%.3f for job %s",
                ordinal_pattern_score,
                countdown_likelihood,
                job_id,
            )
    except Exception as exc:
        logger.warning(
            "Failed to update structural scores for job %s: %s",
            job_id, exc
        )
```

**Step 3** — Wire in `tasks/stage_c.py` after Step 3 (DB result fetch),
before Step 4 (alignment):

```python
# Step 3.5 — Back-populate ordinal/countdown scores from OCR
from ytclfr.probing.ocr_pattern_scorer import score_ocr_patterns

ocr_results = [
    r for r in db_extractor_results
    if r.get("extractor_type") == "ocr"
]
if ocr_results:
    ocr_segs = ocr_results[0].get("segments", [])
    ocr_pattern = score_ocr_patterns(ocr_segs)
    manifest_store.update_structural_scores(
        session,
        job_uuid,
        ordinal_pattern_score=ocr_pattern.ordinal_pattern_score,
        countdown_likelihood=ocr_pattern.countdown_likelihood,
    )
    # Also update structural_video_type to "countdown" if detected
    if (
        ocr_pattern.has_decrementing_sequence
        and manifest
        and manifest.structural_video_type in ("list", "none")
    ):
        # Re-classify as countdown if OCR confirms it
        structural_video_type = "countdown"
        logger.info(
            "Stage C: countdown sequence detected in OCR for job %s — "
            "upgrading structural_video_type to 'countdown'",
            job_id,
        )
```

**Tests to add** (`tests/unit/stage_a/test_ocr_pattern_scorer.py`):
- `test_ordinal_regex_detects_top_n()`
- `test_ordinal_regex_detects_hash_n()`
- `test_countdown_detected_on_clean_sequence()`
- `test_countdown_detected_with_allowed_gaps()`
- `test_no_false_positive_on_speech_text()`
- `test_score_never_raises_on_empty_input()`
- `test_score_returns_zero_on_no_patterns()`

---

## Item E-2 — Fix `countdown_likelihood` (Covered by E-1)

The `ocr_pattern_scorer.py` created in E-1 produces both
`ordinal_pattern_score` and `countdown_likelihood` in one pass.
No separate implementation needed. E-2 is fulfilled by E-1.

**Checkpoint**: After E-1, both `ordinal_pattern_score` and
`countdown_likelihood` in `signal_manifests` will be non-zero for
videos where OCR found ordinal/countdown patterns.

---

## Item E-3 — Fix GET `/results` for V2FinalOutput

**Priority**: P1 (highest impact)
**Effort**: ~3 hours
**Blocks**: Any client consuming the output API for V2-processed jobs

### Context

`V2FinalOutput` records are stored in `final_outputs` with
`content_type = "v2_music"`, `"v2_education"`, etc. The current
GET endpoint returns V1 format for all records.

### Implementation

**Step 1** — Add `V2FinalOutput` response schema to `contracts/v2_output.py`
(verify it already has a full Pydantic model — it does, confirmed).

**Step 2** — Update `api/v1/results.py`:

```python
# At the top of get_job_result():
from ytclfr.contracts.v2_output import V2FinalOutput as V2FinalOutputContract

output = get_cached_result(job_id) or get_final_output_by_job_id(job_id)
if not output:
    raise HTTPException(status_code=404, detail="Result not found")

# V2 path
if output.get("content_type", "").startswith("v2_"):
    try:
        v2 = V2FinalOutputContract.model_validate(output["output_json"])
        return JSONResponse(
            status_code=200,
            content={
                "job_id": job_id,
                "pipeline_version": "v2",
                "content_type": output["content_type"],
                "result": v2.model_dump(mode="json"),
            }
        )
    except Exception as exc:
        logger.error(
            "Failed to deserialize V2FinalOutput for job %s: %s",
            job_id, exc
        )
        raise HTTPException(
            status_code=500,
            detail="V2 result deserialization failed"
        )

# V1 path (unchanged)
return existing_v1_response_logic(output)
```

**Step 3** — Add `pipeline_version` field to the response schema so clients
can detect which format they received without inspecting `content_type`.

**Step 4** — Update OpenAPI docs: add `V2FinalOutput` as a response example.

**Tests to add** (`tests/unit/api/test_results_api.py`):
- `test_get_result_returns_v2_output_for_v2_job()`
- `test_get_result_returns_v1_output_for_v1_job()`
- `test_get_result_404_when_missing()`
- `test_get_result_v2_schema_validates_correctly()`
- `test_get_result_handles_v2_deserialization_failure_gracefully()`

---

## Item E-4 — Fix Retry Endpoint to Route V2 Jobs Through V2 Path

**Priority**: P1
**Effort**: ~2 hours
**Blocks**: Correct recovery behavior for dead-letter V2 jobs

### Context

`POST /api/v1/jobs/{id}/retry` currently dispatches the V1 extractor chord
(`chord(group)(build_timeline.s())`) for all jobs. A V2-era job that was
retried after `dead_letter` would get a V1-format output, bypassing Stage A,
B, C, and D.

### Implementation

**File**: `src/ytclfr/api/v1/jobs.py` (retry handler)

```python
@router.post("/jobs/{job_id}/retry", ...)
async def retry_job(job_id: str, ...):
    job_uuid = UUID(job_id)
    with db_session() as session:
        job = session.query(Job).filter(Job.id == job_uuid).first()
        if not job:
            raise HTTPException(404, "Job not found")

        # Detect pipeline version from existing records.
        # If a SignalManifest exists, this is a V2-era job.
        from ytclfr.storage.manifest_store import SignalManifestStore
        manifest_store = SignalManifestStore()
        manifest = manifest_store.get_by_job_id(session, job_uuid)

        if manifest:
            # V2 path: resume from Stage B (manifest exists, re-dispatch extractors)
            from ytclfr.tasks.stage_b import run_targeted_extraction
            job.status = "stage_a_complete"
            session.commit()
            run_targeted_extraction.delay(job_id)
            return {"job_id": job_id, "resumed_from": "stage_b", "pipeline": "v2"}
        else:
            # V2 path from scratch: signal manifest missing, restart from Stage A
            # (this handles Stage A failures where manifest was never created)
            from ytclfr.db.models.signal_manifest import SignalManifestModel
            manifest_exists_at_all = session.query(SignalManifestModel).filter(
                SignalManifestModel.job_id == job_uuid
            ).first()

            if not manifest_exists_at_all and job.s3_video_uri:
                # V2 job that failed in Stage A — restart from scratch
                from ytclfr.tasks.stage_a import run_signal_census
                job.status = "downloaded"
                session.commit()
                run_signal_census.delay(job_id)
                return {"job_id": job_id, "resumed_from": "stage_a", "pipeline": "v2"}

            # V1 fallback: no S3 URI, no manifest — this is a pre-V2 job
            from ytclfr.tasks.extract import run_asr, run_ocr, run_audio_classifier
            from ytclfr.tasks.align import build_timeline
            from celery import chord, group
            extractor_group = group(
                run_asr.s(job_id),
                run_ocr.s(job_id),
                run_audio_classifier.s(job_id),
            )
            chord(extractor_group)(build_timeline.s(job_id))
            job.status = "extracting"
            session.commit()
            return {"job_id": job_id, "resumed_from": "extractors", "pipeline": "v1"}
```

**Tests to add** (`tests/unit/api/test_retry.py`):
- `test_retry_v2_job_with_manifest_routes_to_stage_b()`
- `test_retry_v2_job_without_manifest_routes_to_stage_a()`
- `test_retry_v1_job_routes_to_v1_extractor_chord()`
- `test_retry_nonexistent_job_returns_404()`

---

## Item E-5 — Wire `asr_expected_value` as Numeric Weight in Conflict Resolver

**Priority**: P2
**Effort**: ~2 hours
**Blocks**: Full ASR confidence discount for music+list videos

### Context

`manifest.asr_expected_value = 0.2` is stored for music+list videos but
the conflict resolver only uses `structural_video_type` as a categorical
switch. The numeric weight is ignored.

### Implementation

**File**: `src/ytclfr/fusion/conflict_resolver.py`

The `resolve_conflicts()` function already receives `manifest`. Extend the
conflict resolution logic:

```python
# ── TUNABLE CONSTANTS ─────────────────────────────────────
ASR_EXPECTED_VALUE_DEFAULT: float = 1.0
OCR_PRIORITY_STRUCTURAL_TYPES: frozenset[str] = frozenset({
    "list", "ranking", "compilation", "countdown", "slideshow"
})


def _effective_asr_confidence(
    segment_confidence: float,
    asr_expected_value: float,
) -> float:
    """Apply asr_expected_value as a discount multiplier.

    For music+list videos: asr_expected_value=0.2 means ASR
    confidence is scaled down to 20% of face value.
    For speech explainers: asr_expected_value=0.5 means
    ASR is at 50% weight.
    Default (1.0) means no discount — full ASR confidence.
    """
    return round(segment_confidence * asr_expected_value, 4)


def resolve_conflicts(
    asr_segments: list[FusedSegment],
    ocr_segments: list[FusedSegment],
    structural_video_type: str,
    manifest: SignalManifest | None,
) -> ConflictResolutionResult:
    asr_expected_value = (
        manifest.asr_expected_value
        if manifest
        else ASR_EXPECTED_VALUE_DEFAULT
    )

    conflict_details = []
    evidence_priority_notes = []

    # For each timestamp where both ASR and OCR have segments,
    # compare effective confidences using the asr discount.
    # ...
    for conflict in _find_temporal_conflicts(asr_segments, ocr_segments):
        effective_asr_conf = _effective_asr_confidence(
            conflict.asr_segment.confidence, asr_expected_value
        )
        effective_ocr_conf = conflict.ocr_segment.confidence

        if effective_ocr_conf >= effective_asr_conf:
            winner = "ocr"
            reason = (
                f"OCR effective_conf={effective_ocr_conf:.3f} >= "
                f"ASR effective_conf={effective_asr_conf:.3f} "
                f"(asr_expected_value={asr_expected_value:.2f})"
            )
        else:
            winner = "asr"
            reason = (
                f"ASR effective_conf={effective_asr_conf:.3f} > "
                f"OCR effective_conf={effective_ocr_conf:.3f}"
            )

        conflict_details.append({
            "timestamp": conflict.timestamp,
            "modalities": ["asr", "ocr"],
            "resolution": winner,
            "reason": reason,
        })
        evidence_priority_notes.append(
            f"t={conflict.timestamp:.1f}s: {winner} preferred. {reason}"
        )

    # Determine primary modality for this video
    if structural_video_type in OCR_PRIORITY_STRUCTURAL_TYPES:
        primary = "ocr" if ocr_segments else "asr"
    else:
        primary = "asr" if asr_segments else (
            "ocr" if ocr_segments else "mixed"
        )

    return ConflictResolutionResult(
        conflict_count=len(conflict_details),
        conflict_details=conflict_details,
        evidence_priority_notes=evidence_priority_notes,
        primary_evidence_modality=primary,
    )
```

**Tests to add** (`tests/unit/stage_c/test_conflict_resolver.py`):
- `test_asr_discounted_when_expected_value_low()`
- `test_ocr_wins_when_asr_discounted_below_ocr_confidence()`
- `test_asr_wins_when_no_discount_and_higher_confidence()`
- `test_asr_expected_value_of_one_is_neutral()`
- `test_structural_type_list_prefers_ocr_primary()`
- `test_structural_type_none_prefers_asr_primary()`
- `test_empty_segments_returns_safe_default()`
- `test_conflict_details_contain_reason_strings()`

---

## Item E-6 — Structural Path Test Coverage

**Priority**: P1 (for long-term stability)
**Effort**: ~4 hours
**Blocks**: Regression safety for the entire structural pipeline

### Context

The structural paths (conflict resolution with `structural_video_type`,
taxonomy with structural override, OCR gating from `ocr_required`) have
no regression tests. This is the primary drift risk.

### Implementation

Create `tests/fixtures/structural_regression_corpus.json`:

```json
{
  "cases": [
    {
      "id": "top-200-songs",
      "description": "Music compilation with ranking titles on screen",
      "has_speech": false,
      "has_music": true,
      "visual_cut_count": 40,
      "overlay_text_density_simulated": 3.5,
      "scene_repeat_score_simulated": 0.75,
      "expected_structural_score_min": 0.55,
      "expected_structural_video_type": "compilation",
      "expected_ocr_required": true,
      "expected_asr_expected_value_max": 0.21
    },
    {
      "id": "product-ranking",
      "description": "Spoken ranking with on-screen numbered overlays",
      "has_speech": true,
      "has_music": false,
      "visual_cut_count": 12,
      "overlay_text_density_simulated": 2.5,
      "scene_repeat_score_simulated": 0.72,
      "expected_structural_score_min": 0.55,
      "expected_structural_video_type": "list",
      "expected_ocr_required": true,
      "expected_asr_expected_value_max": 0.51
    },
    {
      "id": "cooking-tutorial",
      "description": "Speech-only cooking tutorial, no overlays",
      "has_speech": true,
      "has_music": false,
      "visual_cut_count": 3,
      "overlay_text_density_simulated": 0.3,
      "scene_repeat_score_simulated": 0.30,
      "expected_structural_score_min": 0.0,
      "expected_structural_video_type": "none",
      "expected_ocr_required": false,
      "expected_asr_expected_value_max": 0.51
    },
    {
      "id": "slideshow-lecture",
      "description": "Presentation slides, low motion, high text density",
      "has_speech": true,
      "has_music": false,
      "visual_cut_count": 2,
      "overlay_text_density_simulated": 4.0,
      "scene_repeat_score_simulated": 0.80,
      "expected_structural_score_min": 0.55,
      "expected_structural_video_type": "slideshow",
      "expected_ocr_required": true,
      "expected_asr_expected_value_max": 0.51
    },
    {
      "id": "plain-music-video",
      "description": "Single music video, artistic cuts, no text overlay",
      "has_speech": false,
      "has_music": true,
      "visual_cut_count": 25,
      "overlay_text_density_simulated": 0.5,
      "scene_repeat_score_simulated": 0.20,
      "expected_structural_score_min": 0.0,
      "expected_structural_video_type": "none",
      "expected_ocr_required": false,
      "expected_asr_expected_value_max": 0.51
    }
  ]
}
```

Create `tests/unit/stage_a/test_structural_detector_regression.py`:

```python
"""Regression tests for probe_structural() against the golden corpus.

Each test case in the corpus maps to one parametric test. These tests
are the primary guard against threshold drift and detection regression.
They mock probe_structural's internal signals (no video file needed).
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ytclfr.probing.structural_detector import probe_structural


CORPUS_PATH = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "structural_regression_corpus.json"
)

with CORPUS_PATH.open() as f:
    CORPUS = json.load(f)["cases"]


@pytest.mark.parametrize("case", CORPUS, ids=[c["id"] for c in CORPUS])
def test_structural_regression_corpus(case):
    """Each corpus case must produce structural outputs within expected bounds."""
    # Build a minimal frame list that reproduces the simulated densities
    # by patching the inner MSER computation.
    with (
        patch(
            "ytclfr.probing.structural_detector._compute_overlay_density",
            return_value=case["overlay_text_density_simulated"],
        ),
        patch(
            "ytclfr.probing.structural_detector._compute_scene_repeat",
            return_value=case["scene_repeat_score_simulated"],
        ),
    ):
        result = probe_structural(
            sampled_frames=["mock_frame"] * 30,  # non-empty
            visual_cut_count=case["visual_cut_count"],
            visual_motion_density=case.get("visual_motion_density", 5.0),
            has_speech=case["has_speech"],
            has_music=case["has_music"],
        )

    assert result.structural_score >= case["expected_structural_score_min"], (
        f"Case '{case['id']}': structural_score={result.structural_score:.3f} "
        f"< expected_min={case['expected_structural_score_min']}"
    )
    assert result.structural_video_type == case["expected_structural_video_type"], (
        f"Case '{case['id']}': structural_video_type='{result.structural_video_type}' "
        f"!= expected='{case['expected_structural_video_type']}'"
    )
    assert result.ocr_required == case["expected_ocr_required"], (
        f"Case '{case['id']}': ocr_required={result.ocr_required} "
        f"!= expected={case['expected_ocr_required']}"
    )
    assert result.asr_expected_value <= case["expected_asr_expected_value_max"], (
        f"Case '{case['id']}': asr_expected_value={result.asr_expected_value} "
        f"> max={case['expected_asr_expected_value_max']}"
    )
```

Additionally create `tests/unit/stage_b/test_ocr_gating.py`:

```python
"""Unit tests for OCR gating policy in Stage B extractor selection.

These tests enforce the DR-V2-13 policy: OCR must always be dispatched
when ocr_required=True, regardless of any other manifest state.
"""
from unittest.mock import MagicMock
from ytclfr.tasks.stage_b import _build_extractor_names


def _manifest(
    has_speech=True,
    has_music=False,
    has_burned_in_text=False,
    ocr_required=False,
):
    m = MagicMock()
    m.has_speech = has_speech
    m.has_music = has_music
    m.has_burned_in_text = has_burned_in_text
    m.ocr_required = ocr_required
    return m


def test_ocr_required_true_always_dispatches_ocr():
    """DR-V2-13: ocr_required=True must dispatch OCR regardless of other signals."""
    manifest = _manifest(has_speech=False, has_music=False,
                         has_burned_in_text=False, ocr_required=True)
    names = _build_extractor_names(manifest)
    assert "ocr" in names, (
        "ocr_required=True must always include 'ocr' in extractor list"
    )


def test_burned_in_text_dispatches_ocr():
    """Subtitle-bar detection must also force OCR."""
    manifest = _manifest(has_burned_in_text=True, ocr_required=False)
    assert "ocr" in _build_extractor_names(manifest)


def test_no_structural_signal_no_ocr():
    """OCR must not be dispatched when neither burned-in text nor structural."""
    manifest = _manifest(has_burned_in_text=False, ocr_required=False)
    assert "ocr" not in _build_extractor_names(manifest)


def test_metadata_alone_cannot_force_ocr():
    """metadata_prior_confidence is not a dispatch parameter.
    Even high metadata confidence must not cause OCR dispatch."""
    manifest = _manifest(has_burned_in_text=False, ocr_required=False)
    # Even if we set metadata_prior_confidence=0.9, _build_extractor_names
    # does not read it — it only reads ocr_required and has_burned_in_text.
    assert "ocr" not in _build_extractor_names(manifest)


def test_fallback_extractor_when_no_signals():
    """Empty signal set must produce exactly one fallback extractor."""
    manifest = _manifest(
        has_speech=False, has_music=False,
        has_burned_in_text=False, ocr_required=False
    )
    names = _build_extractor_names(manifest)
    assert len(names) == 1
    assert names[0] == "audio"


def test_all_signals_active_dispatches_all_extractors():
    manifest = _manifest(
        has_speech=True, has_music=True,
        has_burned_in_text=True, ocr_required=True
    )
    names = _build_extractor_names(manifest)
    assert set(names) == {"asr", "ocr", "audio"}
```

---

## Item E-7 — Fix S3 Cleanup on Dead-Letter Jobs

**Priority**: P3
**Effort**: ~1 hour
**Blocks**: S3 resource hygiene for permanently failed jobs

### Implementation

**Option A (Immediate, minimal code)** — Dead-letter cleanup in `stage_c.py`
exception handler:

```python
# In the except block of run_fuse_evidence, when job transitions to dead_letter:
except Exception as exc:
    # ... existing error handling ...
    if self.request.retries >= self.max_retries:
        # Permanent failure — clean up S3 to avoid orphans (DR-18)
        try:
            from ytclfr.ingestion.s3_storage import S3StorageManager
            s3_manager = S3StorageManager(settings)
            s3_manager.delete_directory(prefix=f"{job_id}/")
            logger.info(
                "Dead-letter S3 cleanup complete for job %s", job_id
            )
        except Exception as cleanup_exc:
            logger.warning(
                "Dead-letter S3 cleanup failed for job %s: %s",
                job_id, cleanup_exc
            )
```

**Option B (Robust, periodic)** — Add a Celery beat periodic task:

```python
# In tasks/cleanup.py — new file
@celery_app.task(
    name="ytclfr.tasks.cleanup.cleanup_dead_letter_s3",
    queue="io",
)
def cleanup_dead_letter_s3() -> dict:
    """Periodic cleanup: delete S3 objects for dead-letter jobs.

    Runs via Celery beat. Queries for dead_letter jobs with
    non-null s3_video_uri and deletes their S3 directories.
    """
    from ytclfr.db.session import db_session
    from ytclfr.db.models.job import Job
    from ytclfr.ingestion.s3_storage import S3StorageManager
    from ytclfr.core.config import get_settings

    settings = get_settings()
    s3 = S3StorageManager(settings)
    cleaned = 0

    with db_session() as session:
        orphans = (
            session.query(Job)
            .filter(
                Job.status == "dead_letter",
                Job.s3_video_uri.isnot(None),
            )
            .all()
        )
        for job in orphans:
            try:
                s3.delete_directory(prefix=f"{job.id}/")
                job.s3_video_uri = None
                cleaned += 1
            except Exception as exc:
                logger.warning(
                    "Failed to clean S3 for dead_letter job %s: %s",
                    job.id, exc
                )
        session.commit()

    logger.info("Dead-letter S3 cleanup: %d jobs cleaned", cleaned)
    return {"cleaned": cleaned}
```

Implement Option A immediately (one function call in the existing except block).
Add Option B as a separate task when Celery beat is configured.

---

## Item E-8 — Add Deprecation Warning to V1 `classify_video`

**Priority**: P3 (Observability, drift prevention)
**Effort**: 30 minutes
**File**: `src/ytclfr/tasks/route.py`

```python
@celery_app.task(...)
def classify_video(self: Any, job_id: str) -> dict[str, object]:
    """V1 preflight classifier. DEPRECATED — V2 jobs use run_signal_census.

    This task is preserved for backward compatibility with pre-V2 jobs
    and the integration test suite. For all new jobs, ingestion calls
    run_signal_census.delay() directly.

    If this task fires unexpectedly for a V2-era job (one with a
    signal_manifests record), it will produce V1 output, bypassing
    Stage A/B/C/D. This is a routing error and should be investigated.
    """
    logger.warning(
        "V1 classify_video task invoked for job %s. "
        "This is the V1 path and will produce V1-format output. "
        "If this job was ingested after V2 was deployed, this is a "
        "routing error — check ingestion task configuration.",
        job_id,
    )
    # ... rest of existing implementation unchanged ...
```

---

## Execution Order

| Order | Item | Priority | Effort | Unblocks |
|---|---|---|---|---|
| 1 | E-3 GET /results for V2 | P1 | 3h | Client output |
| 2 | E-4 Retry V2 routing | P1 | 2h | Operational recovery |
| 3 | E-6 Structural path tests | P1 | 4h | Regression safety |
| 4 | E-1+E-2 Ordinal/countdown | P2 | 2h | Detection accuracy |
| 5 | E-5 asr_expected_value | P2 | 2h | Fusion precision |
| 6 | E-7 S3 dead-letter cleanup | P3 | 1h | Resource hygiene |
| 7 | E-8 V1 deprecation warning | P3 | 0.5h | Drift prevention |

Total estimated effort: ~14.5 hours.

---

## Definition of Done

All of the following must be true before Stage E is marked COMPLETE:

- [x] `ordinal_pattern_score` is updated from OCR segments in Stage C for structural videos
- [x] `countdown_likelihood` is updated from OCR segments in Stage C
- [x] GET `/api/v1/jobs/{id}/result` returns `V2FinalOutput` for V2-processed jobs
- [x] GET `/results` response includes `pipeline_version` field
- [x] Retry endpoint routes V2-era jobs through Stage B or Stage A (not V1 chord)
- [x] Retry endpoint routes pre-V2 jobs through V1 chord (backward compat)
- [x] `asr_expected_value` is used as a numeric multiplier in conflict resolver
- [x] Conflict resolution `reason` strings appear in `conflict_details`
- [x] Structural regression corpus golden tests pass (5 cases)
- [x] OCR gating policy tests pass (6 tests)
- [x] Conflict resolver structural path tests pass (8 tests)
- [x] Stage D taxonomy structural override tests pass (4 tests)
- [x] S3 cleanup runs on Stage C dead-letter (Option A at minimum)
- [x] V1 `classify_video` logs WARNING on invocation
- [x] `ruff check src/ tests/` — 0 errors
- [x] `mypy src/` — 0 errors
- [x] `pytest tests/unit/ -v` — all existing + new tests pass
- [x] `diff.md` updated for each item
- [x] `build.md` Stage E checkboxes marked
- [x] `decisions.md` updated if any threshold changed