# V2/decisions.md — Architectural Decision Records

Each architectural decision uses this format:

## DR-[N] — [decision title]
Date: [YYYY-MM-DD]
Status: ACCEPTED / SUPERSEDED / UNDER REVIEW
Context: [why this decision was needed]
Decision: [exactly what was decided]
Consequences: [what this enables and what it rules out]
Supersedes: [DR-N if applicable, else NONE]

---

## DR-V2-01 — Evidence-Based Late Binding replaces RouterDecision
Date: 2026-05-23
Status: ACCEPTED
Context: V1 RouterDecision forces a single content-type label
  before content analysis runs. This produces incorrect output
  when signals do not match the title heuristic.
Decision: V1 contracts/router.py and router/classifier.py are
  deprecated. Stage A produces a SignalManifest — a multi-signal
  evidence object — with no content-type classification.
  Classification runs only in Stage D after all evidence exists.
Consequences: No extractor runs before a manifest exists.
  The manifest drives Stage B's dynamic Celery group. V1 tables
  remain until a cleanup migration removes them after V2 is live.
Supersedes: NONE

---

## DR-V2-02 — Probers are pure functions with no infrastructure deps
Date: 2026-05-23
Status: ACCEPTED
Context: probe_audio, probe_visual, and probe_metadata could be
  written as Celery tasks or as plain functions. Making them
  Celery tasks adds broker overhead and makes unit testing harder.
Decision: All three probers are pure functions that accept file
  paths and return dataclass results. The single Celery task
  `run_signal_census` orchestrates them sequentially. This keeps
  probing logic testable without Redis/PostgreSQL infrastructure.
Consequences: Probers run in-process inside the Celery worker.
  They cannot be distributed across multiple workers. This is
  acceptable because probe_audio and probe_visual together
  complete in < 90s on the ThinkPad L13.
Supersedes: NONE

---

## DR-V2-03 — Windows-compatible timeout via threading.Timer
Date: 2026-05-23
Status: ACCEPTED
Context: The original design used `signal.alarm()` for timeout
  guards in probe_audio and probe_visual. `signal.alarm()` is
  not available on Windows, which is the primary development
  platform (ThinkPad L13).
Decision: Replace `signal.alarm()` with `threading.Timer` +
  `threading.Event` for timeout detection. A daemon timer sets
  an event flag; each major probe step checks the flag and raises
  an internal `_TimeoutError` if set.
Consequences: Timeout granularity is limited to the check points
  between probe steps (not truly preemptive). A single long-running
  OpenCV or librosa call cannot be interrupted mid-operation. This
  is acceptable because each individual operation has its own
  subprocess timeout (ffprobe: 30s, ffmpeg: 60s) or data cap
  (librosa: duration=60.0s).
Supersedes: NONE

---

## DR-V2-04 — Stage A downloads from S3 transiently for probing
Date: 2026-05-24
Status: ACCEPTED
Context: Phase 10 (DR-18) makes all workers stateless — videos
  are deleted locally after S3 upload. Stage A needs the video
  file to run probe_audio and probe_visual. job.local_media_path
  is None on all post-ingestion worker nodes.
Decision: If job.local_media_path is absent or does not exist,
  Stage A downloads the video from S3 to a transient scratch path
  (TempStorageManager + S3StorageManager). The file is named
  video_probe.mp4 to avoid colliding with video.mp4 used by
  extract tasks. The finally block deletes it unconditionally,
  keeping the node stateless.
Consequences: Stage A adds one S3 download round-trip per job.
  This is the same pattern as run_asr and run_ocr (tasks/extract.py).
  CPU-only nodes never accumulate video files. No local path is
  assumed or required.
Supersedes: NONE

---

## DR-V2-05 — Stage B uses dynamic Celery group, not static chord
Date: 2026-05-24
Status: ACCEPTED
Context: V1 classify_video blindly fires group(run_asr, run_ocr,
  run_audio_classifier) for every video regardless of content.
  A music-only video does not need ASR. A silent screen recording
  does not need audio classification.
Decision: Stage B reads the SignalManifest and builds a list of
  extractors dynamically using _build_extractor_names(manifest).
  has_speech → run_asr. has_burned_in_text → run_ocr.
  has_speech OR has_music → run_audio_classifier.
  If all signals are False → run_audio_classifier as fallback
  (it uses DB metadata only, no S3 download required).
  The dynamic list is passed to Celery group(*tasks_to_run).
Consequences: CPU usage scales with content. A silent video
  skips both Whisper (ASR) and Tesseract (OCR). The fallback
  guarantees build_timeline always receives at least one chord
  result. Duplicate extractor names are impossible by construction.
Supersedes: NONE

---

## DR-V2-06 — Stage B chord callback is build_timeline (temporary)
Date: 2026-05-24
Status: SUPERSEDED
Superseded by: DR-V2-08
Context: Stage C (Evidence Fusion) does not exist yet. The chord
  group needs a callback that runs after all extractors complete.
  The existing build_timeline function in tasks/align.py already
  performs temporal alignment and confidence evaluation.
Decision: Stage B fires chord(group(*))(build_timeline.s(job_id)).
  build_timeline is the temporary Stage C placeholder. It is
  marked # STAGE-C-TODO in tasks/stage_b.py. When Stage C is
  built, this single line changes to run_fuse_evidence.s(job_id).
Consequences: V1 alignment engine remains active in the V2 path.
  Stage C can be plugged in with a one-line change. V1 output
  quality is preserved while Stage B is being validated.
Supersedes: NONE

---

## DR-V2-07 — _build_extractor_names is a pure testable function
Date: 2026-05-24
Status: ACCEPTED
Context: The dynamic group logic (which extractors fire for which
  signals) is the critical business logic of Stage B. Embedding it
  inside the Celery task body makes it impossible to unit-test
  without mocking Celery, DB, and Redis.
Decision: The selection logic lives in _build_extractor_names(manifest)
  — a pure function with no infrastructure dependencies. The Celery
  task calls this function and then maps names to .s(job_id) signatures.
  This enables direct unit testing against the golden fixture.
Consequences: Selection logic is covered by 7 unit tests. Adding a
  new extractor type in Stage C/D requires only adding a branch in
  _build_extractor_names and a test. No Celery mocking needed.
Supersedes: NONE



## DR-V2-08 — run_fuse_evidence replaces build_timeline as Stage B chord callback
Date: 2026-05-25
Status: ACCEPTED
Context: Stage B fires chord(group(extractors))(build_timeline.s()).
  build_timeline is the V1 chord callback in tasks/align.py. It
  runs V1 alignment and calls assemble_and_save_final_output().
  Stage C needs to intercept this flow to add entity extraction
  and Groq reasoning before Stage D produces the V2 FinalOutput.
Decision: run_fuse_evidence (tasks/stage_c.py) replaces
  build_timeline as Stage B's chord callback. Stage B is updated
  to call chord(group)(run_fuse_evidence.s(job_id)).
  build_timeline is NOT deleted — it remains for the V1 path
  (classify_video still fires it). Chord signature matches
  build_timeline exactly: (extractor_results, job_id).
Consequences: V2 jobs go through run_fuse_evidence → EvidenceGraph
  → Stage D. V1 jobs (via classify_video) still use build_timeline
  → aligned_segments → final_output (V1 path unchanged).
  run_fuse_evidence calls align() and save_aligned_segments()
  for backward compatibility with V1 API endpoints.
Supersedes: DR-V2-06 (partially — the callback identity changes
  but the "temporary" reasoning remains valid during Stage D build)

## DR-V2-09 — Stage C still runs V1 alignment for backward compatibility
Date: 2026-05-25
Status: ACCEPTED
Context: V1 API endpoints (GET /api/v1/jobs/{id}/results) read from
  the aligned_segments table. If Stage C stops saving aligned_segments,
  the V1 API breaks for jobs processed by the V2 path.
Decision: run_fuse_evidence calls align() and save_aligned_segments()
  before entity extraction and Groq reasoning. This populates the
  aligned_segments table. Stage C does NOT call
  assemble_and_save_final_output() — that V1 function produces a
  V1 FinalOutput. Stage D will produce the V2 FinalOutput.
Consequences: aligned_segments table stays consistent for all jobs
  regardless of V1 or V2 path. The V1 GET /results API continues
  to work. Stage D can optionally read aligned_segments or the
  EvidenceGraph — both are available.
Supersedes: NONE

## DR-V2-10 — Groq reasoning is optional and degrades gracefully
Date: 2026-05-25
Status: ACCEPTED
Context: Groq is a cloud API with potential for network failure,
  rate limiting, or missing API key. Stage C cannot block or fail
  if Groq is unavailable. The pipeline must complete regardless.
Decision: groq_reasoner.reason_over_evidence() never raises.
  If GROQ_API_KEY is empty, it returns immediately without a
  network call. If any exception occurs, it returns
  _GROQ_FAILURE_RESULT with reasoning_used=False. The
  EvidenceGraph is still created and persisted; dominant_subject,
  groq_summary, and scene_boundaries will be None or [0.0].
  Stage D must handle this gracefully when GROQ_API_KEY is absent.
Consequences: Pipeline works end-to-end without Groq credentials.
  Users without Groq API access get a structural EvidenceGraph
  with entities from heuristic extraction only. Stage D design
  must account for missing Groq fields.
Supersedes: NONE

## DR-V2-11 — Stage D persists V2FinalOutput to existing final_outputs table
Date: 2026-05-25
Status: ACCEPTED
Context: Stage D produces a richer V2 output (taxonomy, summary, items, evidence provenance) that is structurally incompatible with the V1 FinalOutput schema (content_type, video_metadata, items, script). Adding a new DB table would require a new migration and break the V1 results API.
Decision: Stage D writes V2FinalOutput to the existing final_outputs table using output_json (JSON column). content_type is set to "v2_" + parent_category (e.g., "v2_education"). The V2_CONTENT_TYPE_PREFIX "v2_" distinguishes V2 records from V1 records. V1 API endpoint updates are deferred to Pipeline Wiring (W-6).
Consequences: No new Alembic migration needed. V1 API (GET /results) will return a V2 dict for V2-path jobs until W-6 is applied. Stage D is idempotent: it checks for content_type.startswith("v2_") before re-running.
Supersedes: NONE

## DR-V2-12 — Taxonomy classification is Groq-first, rule-based fallback
Date: 2026-05-25
Status: ACCEPTED
Context: Groq provides rich taxonomy classification but may be unavailable (no API key, network failure, rate limiting). Stage D cannot block or fail if Groq is unavailable.
Decision: taxonomy/mapper.py calls Groq first. On any failure or missing key, it calls taxonomy/intent_resolver.py which uses SUBJECT_KEYWORD_MAP against dominant_subject + signal flags. V2FinalOutput.taxonomy.groq_taxonomy_used records which path ran. The rule-based fallback always produces a valid TaxonomyFallback.
Consequences: Every V2 job gets taxonomy even without Groq. Groq taxonomy confidence is typically 0.7–0.95. Rule-based fallback confidence is 0.55 (or lower for fully ambiguous content). Stage D never fails due to missing taxonomy.
Supersedes: NONE

## DR-V2-13 — taxonomy/ and fusion/ are pure-function packages
Date: 2026-05-25
Status: ACCEPTED
Context: taxonomy/mapper.py and taxonomy/intent_resolver.py contain the core classification business logic of Stage D. Embedding this logic in the Celery task body makes it impossible to unit-test without mocking Celery, DB, and Redis.
Decision: All classification logic lives in pure functions. tasks/stage_d.py calls them and handles infrastructure concerns. Circular import between mapper.py and intent_resolver.py is avoided by defining TaxonomyFallback in intent_resolver.py and importing it into mapper.py (one-way dependency).
Consequences: Classification logic is testable without any infrastructure. mapper.py has 6 tests, intent_resolver.py has 8 tests, all pure-function tests with no mocking complexity.
Supersedes: NONE
