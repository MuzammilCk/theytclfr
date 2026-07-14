# Phase 9: End-to-End Hardening - Runbook

## 1. Incident: S3 Outage / Credentials Expired
**Symptoms:** 
- `download_video` or S3 upload/download tasks repeatedly failing.
- Jobs marked as `dead_letter`.
- Logs show S3 authorization errors or timeouts.

**Recovery:**
1. Update AWS environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
2. Restart workers or API if credentials are baked in at startup.
3. Call the `POST /api/v3/jobs/{job_id}/retry` endpoint for the affected `dead_letter` jobs. The system will detect if `s3_video_uri` is missing and resume from `download_video`.

## 2. Incident: Redis OOM / Connection Lost
**Symptoms:**
- Celery worker stops accepting new tasks.
- Connection timeouts in API or worker logs.
- Jobs stuck in `pending` or midway without advancing.

**Recovery:**
1. Restart the Redis service (`sudo systemctl restart redis` or Docker equivalent).
2. For any jobs that were actively processing and failed permanently (transitioning to `dead_letter` after retries), call `POST /api/v3/jobs/{job_id}/retry`.
3. Check `GET /api/v3/metrics` to ensure job pipeline resumes successfully.

## 3. Incident: Ollama Process Killed (OOM)
**Symptoms:**
- Alignment/inference tasks (`build_timeline` or `run_audio_classifier`) timeout or return connection errors.
- `dmesg` shows Ollama process killed by OOM-killer.

**Recovery:**
1. Ensure Ollama is running and has sufficient memory (`ollama serve`).
2. Any jobs that failed during extraction or alignment will be marked `dead_letter`.
3. Call `POST /api/v3/jobs/{job_id}/retry`. The pipeline will resume from the extraction or alignment phase without redownloading from S3.

## 4. Incident: Invalid YouTube URL bypasses frontend
**Symptoms:**
- Job created but fails immediately during validation or initial download attempt.

**Outcome:**
- Validation will throw a 422 Unprocessable Entity in the API.
- If it passes regex but fails resolution, `yt-dlp` will fail. The job will eventually reach `failed` or `dead_letter` status.
- **No retry required.** Do not call the retry endpoint for invalid URLs.

## 5. Incident: Groq API Rate Limit or Connectivity Failure
**Symptoms:**
- Stage C (`run_fuse_evidence`) and Stage D (`run_taxonomy_mapping`) warn about Groq reasoning failure.
- Taxonomy and reasoning fall back to rule-based execution.
- `groq_reasoning_used` or `groq_used` in final payload is `False`.

**Recovery:**
1. Check `GROQ_API_KEY` configuration and Groq status page.
2. The pipeline is designed to degrade gracefully. If rule-based results are acceptable, no action is needed.
3. If Groq-based reasoning is strictly required for those jobs, you must manually run `POST /api/v3/jobs/{job_id}/retry` after restoring API access.

## 6. Incident: V3 Task Unregistered
**Symptoms:**
- Error in Celery log: `Received unregistered task of type 'ytclfr.tasks.v3...'`.
- V3 pipeline jobs stuck after download stage.

**Recovery:**
1. This is a code/deployment issue. V3 tasks must be explicitly imported in `src/ytclfr/queue/celery_app.py`.
2. Add the missing `import ytclfr.tasks.v3...` statement.
3. Restart Celery worker to load the new imports.

## 7. Incident: V3 Stage Stall
**Symptoms:**
- Job status stuck at `v3_stage_X_running` for longer than expected.
- No active tasks shown in Celery for the job.

**Recovery:**
1. Check Celery logs for exceptions in the current stage or failures to invoke the next stage in the chain.
2. If the previous stage completed but failed to trigger the callback, manually set the job status back to the previous completed state or trigger the retry API.

## 8. Incident: V3 ASR Degradation False Positive
**Symptoms:**
- OCR overweighted for a speech-heavy video resulting in poor fusion.

**Recovery:**
1. Check `v3_extractor_bundles.asr_metrics_json` for `untranscribed_speech_ratio` and `is_degraded` flag.
2. If the degradation flag was incorrectly set due to long periods of silence, the tuning of `ASRCompletenessMetrics` thresholds may need adjustment.
