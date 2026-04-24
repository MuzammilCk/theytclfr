# Phase 9: End-to-End Hardening - Runbook

## 1. Incident: S3 Outage / Credentials Expired
**Symptoms:** 
- `download_video` or S3 upload/download tasks repeatedly failing.
- Jobs marked as `dead_letter`.
- Logs show S3 authorization errors or timeouts.

**Recovery:**
1. Update AWS environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
2. Restart workers or API if credentials are baked in at startup.
3. Call the `POST /api/v1/jobs/{job_id}/retry` endpoint for the affected `dead_letter` jobs. The system will detect if `s3_video_uri` is missing and resume from `download_video`.

## 2. Incident: Redis OOM / Connection Lost
**Symptoms:**
- Celery worker stops accepting new tasks.
- Connection timeouts in API or worker logs.
- Jobs stuck in `pending` or midway without advancing.

**Recovery:**
1. Restart the Redis service (`sudo systemctl restart redis` or Docker equivalent).
2. For any jobs that were actively processing and failed permanently (transitioning to `dead_letter` after retries), call `POST /api/v1/jobs/{job_id}/retry`.
3. Check `GET /api/v1/metrics` to ensure job pipeline resumes successfully.

## 3. Incident: Ollama Process Killed (OOM)
**Symptoms:**
- Alignment/inference tasks (`build_timeline` or `run_audio_classifier`) timeout or return connection errors.
- `dmesg` shows Ollama process killed by OOM-killer.

**Recovery:**
1. Ensure Ollama is running and has sufficient memory (`ollama serve`).
2. Any jobs that failed during extraction or alignment will be marked `dead_letter`.
3. Call `POST /api/v1/jobs/{job_id}/retry`. The pipeline will resume from the extraction or alignment phase without redownloading from S3.

## 4. Incident: Invalid YouTube URL bypasses frontend
**Symptoms:**
- Job created but fails immediately during validation or initial download attempt.

**Outcome:**
- Validation will throw a 422 Unprocessable Entity in the API.
- If it passes regex but fails resolution, `yt-dlp` will fail. The job will eventually reach `failed` or `dead_letter` status.
- **No retry required.** Do not call the retry endpoint for invalid URLs.
