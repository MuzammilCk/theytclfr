from enum import Enum
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ytclfr.api.auth import require_auth
from ytclfr.db.session import get_db
from ytclfr.storage.queries import get_final_output_by_job_id
from ytclfr.contracts.v3.response import FinalResponse

router = APIRouter(prefix="/jobs/{job_id}", tags=["results"])


def _unwrap(val, key: str):
    """The V3 evidence JSON columns are stored as single-key dicts
    (e.g. ``{"segments": [...]}``); some default to plain lists. Normalise
    both shapes to the flat list the contract expects."""
    if isinstance(val, dict) and key in val:
        return val[key]
    if isinstance(val, list):
        return val
    return []

class ViewMode(str, Enum):
    BASIC = "BASIC"
    FULL = "FULL"
    DEBUG = "DEBUG"

@router.get("/result", response_model=None)
def get_v3_job_result(
    job_id: UUID,
    view: ViewMode = Query(ViewMode.BASIC, description="Resource view level"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    output_model = get_final_output_by_job_id(job_id, db)
    if not output_model:
        raise HTTPException(status_code=404, detail="Job result not found")

    if not output_model.content_type.startswith("v3_"):
        raise HTTPException(status_code=400, detail="Requested V3 result but job was processed by legacy pipeline")

    result_dict = output_model.output_json
    
    try:
        validated_response = FinalResponse.model_validate(result_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"V3 schema validation failed: {e}")

    response_dict = validated_response.model_dump(mode="json")
    response_dict["schema_version"] = "v3"

    if view in (ViewMode.FULL, ViewMode.DEBUG):
        # Attach internal state
        from ytclfr.storage.manifest_store import SignalManifestStore
        from ytclfr.db.models.v3.v3_extractor_bundles import V3ExtractorBundleORM

        manifest = SignalManifestStore().get_by_job_id(db, job_id)
        if manifest:
            response_dict["_debug_manifest"] = manifest.model_dump(mode="json")
            
        bundle = db.query(V3ExtractorBundleORM).filter(V3ExtractorBundleORM.job_id == job_id).first()
        if bundle:
            response_dict["_debug_bundle"] = {
                "asr_segments": bundle.asr_segments_json,
                "ocr_segments": bundle.ocr_segments_json,
                "audio_segments": bundle.audio_segments_json,
                "asr_metrics": bundle.asr_metrics_json,
            }

    if view == ViewMode.DEBUG:
        from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM
        evidence = db.query(V3EvidenceGraphORM).filter(V3EvidenceGraphORM.job_id == job_id).first()
        if evidence:
            response_dict["_debug_evidence_graph"] = {
                "job_id": str(evidence.job_id),
                "segments": _unwrap(evidence.segments_json, "segments"),
                "entities": _unwrap(evidence.entities_json, "entities"),
                "dominant_subject": evidence.dominant_subject,
                "groq_summary": evidence.groq_summary,
                "scene_boundaries": evidence.scene_boundaries_json or [],
                "groq_reasoning_used": evidence.groq_reasoning_used,
                "modality_coverage": evidence.modality_coverage_json or {},
                "conflict_count": evidence.conflict_count,
                "conflict_details": _unwrap(evidence.conflict_details_json, "conflict_details"),
                "structural_video_type": evidence.structural_video_type,
                "evidence_priority_notes": evidence.evidence_priority_notes_json or [],
                "primary_evidence_modality": evidence.primary_evidence_modality,
                "total_segments": evidence.total_segments,
                "confidence": evidence.confidence,
                "created_at": evidence.created_at.isoformat() if evidence.created_at else "",
            }

    return JSONResponse(content=response_dict)
