from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ytclfr.api.auth import require_auth
from ytclfr.core.config import get_settings
from ytclfr.db.models.job import Job
from ytclfr.db.session import get_db
from ytclfr.storage.embeddings import generate_embedding
from ytclfr.storage.queries import (
    search_segments_by_keyword,
    search_segments_by_similarity,
    search_v3_evidence_keyword,
)

router = APIRouter(prefix="/jobs/{job_id}", tags=["search"])


@router.get("/search")
def search_job_segments(
    job_id: UUID,
    q: str = Query(..., min_length=1, description="Search query"),
    mode: Literal["keyword", "similarity"] = Query(
        "keyword", description="keyword = lexical; similarity = pgvector cosine"
    ),
    limit: int = Query(25, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
    _token: object = Depends(require_auth),
) -> dict:
    """Search a job's extracted transcript / OCR.

    Keyword mode searches both the legacy ``aligned_segments`` table and the
    V3 evidence-graph JSON. Similarity mode embeds the query and runs a pgvector
    cosine search (requires Ollama embeddings to be available).
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    results: list[dict] = []
    if mode == "similarity":
        vec = generate_embedding(q, get_settings())
        if vec is None:
            raise HTTPException(
                status_code=502,
                detail="Embedding service unavailable (Ollama offline?)",
            )
        results = search_segments_by_similarity(job_id, vec, db)
        # graceful fallback to lexical if vector search is empty
        if not results:
            results = search_segments_by_keyword(job_id, q, db)
    else:
        results = search_segments_by_keyword(job_id, q, db)
        results.extend(search_v3_evidence_keyword(job_id, q, db))

    # Deduplicate (start_seconds + leading text) and sort by timeline.
    seen: set[tuple] = set()
    merged: list[dict] = []
    for r in sorted(results, key=lambda x: x.get("start_seconds") or 0):
        key = (round(r.get("start_seconds") or 0, 2), (r.get("text") or "")[:40])
        if key in seen:
            continue
        seen.add(key)
        merged.append(r)

    return {
        "job_id": str(job_id),
        "mode": mode,
        "query": q,
        "count": len(merged[:limit]),
        "results": merged[:limit],
    }
