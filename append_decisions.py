import io

decisions_text = """

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
"""

with io.open('v2/decisions.md', 'a', encoding='utf-8') as f:
    f.write(decisions_text)
