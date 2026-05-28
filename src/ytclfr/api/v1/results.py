from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ytclfr.api.auth import require_auth
from ytclfr.core.config import get_settings
from ytclfr.db.session import get_db
from ytclfr.storage.queries import (
    get_final_output_by_job_id,
    get_segments_by_time_range,
    search_segments_by_keyword,
    search_segments_by_similarity,
)
from ytclfr.storage.embeddings import generate_embedding
from ytclfr.cache.result_cache import get_cached_result, cache_result
from ytclfr.contracts.output import FinalOutput

router = APIRouter(prefix="/jobs/{job_id}", tags=["results"])

class SegmentResult(BaseModel):
    start_seconds: float
    end_seconds: float | None
    text: str
    source: str
    confidence: float

class SegmentQueryResponse(BaseModel):
    segments: list[SegmentResult]

@router.get("/result", response_model=None)
def get_job_result(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    cached = get_cached_result(job_id)
    if cached:
        return JSONResponse(content=cached)

    output_model = get_final_output_by_job_id(job_id, db)
    if not output_model:
        raise HTTPException(status_code=404, detail="Job result not found")

    result_dict = output_model.output_json
    if output_model.content_type and output_model.content_type.startswith("v3_"):
        raise HTTPException(status_code=400, detail="This is a V3 job. Please use the /api/v3/jobs/{job_id}/result endpoint.")
    
    if output_model.content_type and output_model.content_type.startswith("v2_"):
        from ytclfr.contracts.v2_output import V2FinalOutput
        try:
            validated = V2FinalOutput.model_validate(result_dict)
            result_dict = validated.model_dump(mode="json")
        except Exception as e:
            # If validation fails, we still return the raw dict but log the error (or just fallback)
            pass
        result_dict["schema_version"] = "v2"
        result_dict["pipeline_version"] = "v2.2.0"
    else:
        result_dict["schema_version"] = "v1"

    settings = get_settings()
    cache_result(job_id, result_dict, settings.redis_result_cache_ttl)
    
    return JSONResponse(content=result_dict)

@router.get("/segments", response_model=SegmentQueryResponse)
def get_job_segments(
    job_id: UUID,
    start_sec: float = Query(..., description="Start time in seconds"),
    end_sec: float = Query(..., description="End time in seconds"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    segments = get_segments_by_time_range(job_id, start_sec, end_sec, db)
    return {"segments": segments}

@router.get("/search", response_model=SegmentQueryResponse)
def search_job_segments(
    job_id: UUID,
    query: str = Query(..., description="Keyword search query"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    segments = search_segments_by_keyword(job_id, query, db)
    return {"segments": segments}

@router.get("/similar", response_model=SegmentQueryResponse)
def get_similar_segments(
    job_id: UUID,
    query: str = Query(..., description="Semantic search query"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    settings = get_settings()
    embedding = generate_embedding(query, settings)
    if not embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding for query")

    segments = search_segments_by_similarity(job_id, embedding, db)
    return {"segments": segments}
