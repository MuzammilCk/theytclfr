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
