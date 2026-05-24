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
Status: ACCEPTED
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

