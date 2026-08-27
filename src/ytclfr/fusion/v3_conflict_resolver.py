import logging
from dataclasses import dataclass, field
from typing import Any

from ytclfr.contracts.v3.evidence import FusedSegment
from ytclfr.contracts.v3.manifest import SignalManifest
from ytclfr.contracts.v3.bundle import ASRCompletenessMetrics

logger = logging.getLogger(__name__)

@dataclass
class V3ConflictResolution:
    conflict_count: int
    conflict_details: list[dict[str, Any]]
    primary_evidence_modality: str
    evidence_priority_notes: list[str] = field(default_factory=list)
    adjusted_asr_segments: list[FusedSegment] | None = None
    adjusted_ocr_segments: list[FusedSegment] | None = None


def v3_resolve_conflicts(
    asr_segments: list[FusedSegment],
    ocr_segments: list[FusedSegment],
    structural_video_type: str,
    manifest: SignalManifest,
    asr_metrics: ASRCompletenessMetrics | None,
) -> V3ConflictResolution:
    conflict_count = 0
    conflict_details: list[dict[str, Any]] = []
    notes: list[str] = []
    primary_modality = "mixed"

    has_ocr = len(ocr_segments) > 0
    has_asr = len(asr_segments) > 0
    is_structural = structural_video_type != "none"
    is_degraded_asr = asr_metrics is not None and asr_metrics.is_degraded

    if is_structural:
        if has_ocr:
            primary_modality = "ocr"
            notes.append(
                f"Structural video ({structural_video_type}) with OCR present. "
                "OCR prioritized for taxonomy."
            )
        else:
            primary_modality = "mixed"
            notes.append(
                f"Structural video ({structural_video_type}) but OCR is missing. "
                "Falling back to mixed evidence."
            )
    elif is_degraded_asr:
        if has_ocr:
            primary_modality = "ocr"
            notes.append("ASR is heavily degraded. OCR prioritized.")
        else:
            primary_modality = "mixed"
            notes.append("ASR is heavily degraded and no OCR present. Mixed evidence.")
    else:
        if manifest.has_speech:
            primary_modality = "asr"
            notes.append("Speech-heavy non-structural video. ASR prioritized.")
        elif has_ocr and not has_asr:
            primary_modality = "ocr"
            notes.append("No speech detected but OCR present. OCR prioritized.")
        else:
            primary_modality = "mixed"
            notes.append("No strong modality preference detected.")

    adjusted_ocr_segments = None
    adjusted_asr_segments = None
    
    if has_asr and has_ocr:
        if is_structural or is_degraded_asr:
            conflict_count += 1
            reason = "Structural video dictates OCR priority" if is_structural else "Degraded ASR dictates OCR priority"
            conflict_details.append(
                {
                    "type": "modality_priority",
                    "description": f"ASR suppressed in favor of OCR. Reason: {reason}",
                    "resolution": "ocr_wins",
                }
            )
            # Boost OCR
            adjusted_ocr_segments = []
            for seg in ocr_segments:
                new_conf = min(1.0, seg.confidence * 1.5)
                adjusted_ocr_segments.append(seg.model_copy(update={"confidence": new_conf}))
                
            # Discount ASR
            adjusted_asr_segments = []
            for seg in asr_segments:
                new_conf = seg.confidence * 0.5
                adjusted_asr_segments.append(seg.model_copy(update={"confidence": new_conf}))
                
    if has_asr and adjusted_asr_segments is None and manifest.asr_expected_value < 0.5:
        notes.append(f"ASR expected value is low ({manifest.asr_expected_value}). Discounting ASR segment confidences.")
        adjusted_asr_segments = []
        for seg in asr_segments:
            new_conf = seg.confidence * manifest.asr_expected_value
            adjusted_asr_segments.append(seg.model_copy(update={"confidence": new_conf}))

    return V3ConflictResolution(
        conflict_count=conflict_count,
        conflict_details=conflict_details,
        primary_evidence_modality=primary_modality,
        evidence_priority_notes=notes,
        adjusted_asr_segments=adjusted_asr_segments,
        adjusted_ocr_segments=adjusted_ocr_segments,
    )
