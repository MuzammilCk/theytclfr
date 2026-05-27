"""Conflict resolution logic for Stage C late fusion.

Implements Evidence Priority Rules:
1. structural_video + OCR text → OCR outranks ASR for taxonomy
2. speech-heavy + no structure → ASR dominates
3. both modalities agree → highest confidence wins
4. OCR missing on structural video → lower confidence, fallback note
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from ytclfr.contracts.evidence import FusedSegment
from ytclfr.contracts.manifest import SignalManifest

logger = logging.getLogger(__name__)


@dataclass
class ConflictResolution:
    conflict_count: int
    conflict_details: list[dict[str, Any]]
    primary_evidence_modality: str
    evidence_priority_notes: list[str] = field(default_factory=list)
    adjusted_asr_segments: list[FusedSegment] | None = None


def resolve_conflicts(
    asr_segments: list[FusedSegment],
    ocr_segments: list[FusedSegment],
    structural_video_type: str,
    manifest: SignalManifest,
) -> ConflictResolution:
    """Resolve conflicts between ASR and OCR evidence.

    Uses structural context to determine which modality should
    be prioritized when they present differing subjects or when
    we need to establish the primary evidence source.
    """
    conflict_count = 0
    conflict_details: list[dict[str, Any]] = []
    notes: list[str] = []
    primary_modality = "mixed"

    has_ocr = len(ocr_segments) > 0
    has_asr = len(asr_segments) > 0

    is_structural = structural_video_type != "none"

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
                "Falling back to mixed evidence with reduced confidence."
            )
            # We don't adjust confidence here; stage_d/stage_c logic handles it,
            # but we record the note.
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

    # A simple cross-modality check could go here if we compare themes
    # e.g., if ASR contains 'lyrics' but OCR contains numbers, we note it.
    if has_asr and has_ocr and is_structural:
        conflict_count += 1
        conflict_details.append(
            {
                "type": "modality_priority",
                "description": "ASR (likely lyrics) suppressed in favor of OCR (list structure)",
                "resolution": "ocr_wins",
            }
        )
        
    # E-5: Apply numeric ASR confidence discount based on manifest expectation
    adjusted_asr_segments = None
    if has_asr and manifest.asr_expected_value < 0.5:
        notes.append(f"ASR expected value is low ({manifest.asr_expected_value}). Discounting ASR segment confidences.")
        adjusted_asr_segments = []
        for seg in asr_segments:
            new_conf = seg.confidence * manifest.asr_expected_value
            adjusted_asr_segments.append(seg.model_copy(update={"confidence": new_conf}))

    return ConflictResolution(
        conflict_count=conflict_count,
        conflict_details=conflict_details,
        primary_evidence_modality=primary_modality,
        evidence_priority_notes=notes,
        adjusted_asr_segments=adjusted_asr_segments,
    )
