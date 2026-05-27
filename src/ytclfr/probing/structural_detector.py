"""Structural video detector for Stage A.

Detects if a video has a list, ranking, countdown, compilation,
slideshow, or infographic structure. This is used to force OCR
even if no subtitle bar is present.

Pure function, no infrastructure dependencies. CPU-only.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ── TUNABLE CONSTANTS ───────────────────────────────────────────────
STRUCTURAL_SCORE_THRESHOLD: float = 0.55
LIST_LIKELIHOOD_THRESHOLD: float = 0.60
OVERLAY_DENSITY_HIGH: float = 2.0  # avg text regions per frame
ORDINAL_PATTERN_MIN_HITS: int = 3
SCENE_REPEAT_SIMILARITY_THRESHOLD: float = 0.70

# Regex for detecting list ordinals (e.g., "#1", "Top 10", "No. 5")
ORDINAL_REGEX = re.compile(
    r"(?i)\b(?:top\s*\d+|#\s*\d+|no\.?\s*\d+|\d+(?:st|nd|rd|th))\b"
)


@dataclass
class StructuralProbeResult:
    """Result of structural probing for Stage A."""

    structural_score: float
    list_likelihood: float
    countdown_likelihood: float
    overlay_text_density: float
    ordinal_pattern_score: float
    scene_repeat_score: float
    ocr_required: bool
    ocr_expected_coverage: float
    asr_expected_value: float
    structural_video_type: Literal[
        "none", "list", "ranking", "countdown",
        "compilation", "slideshow", "infographic", "unknown"
    ]


def probe_structural(
    sampled_frames: list[Any],
    visual_cut_count: int,
    visual_motion_density: float,
    has_speech: bool,
    has_music: bool,
    metadata_prior_confidence: float = 0.5,
) -> StructuralProbeResult:
    """Detect structural video patterns from sampled frames.

    Args:
        sampled_frames: List of OpenCV frames from visual prober.
        visual_cut_count: Number of scene cuts detected.
        visual_motion_density: Scene cuts per minute.
        has_speech: Voice detected.
        has_music: Music detected.
        metadata_prior_confidence: Confidence in metadata accuracy.

    Returns:
        StructuralProbeResult. Never raises.
    """
    try:
        return _probe_structural_inner(
            sampled_frames,
            visual_cut_count,
            visual_motion_density,
            has_speech,
            has_music,
            metadata_prior_confidence,
        )
    except Exception as exc:
        logger.error(
            "Structural probe unexpected failure: %s",
            exc,
            exc_info=True,
        )
        return StructuralProbeResult(
            structural_score=0.0,
            list_likelihood=0.0,
            countdown_likelihood=0.0,
            overlay_text_density=0.0,
            ordinal_pattern_score=0.0,
            scene_repeat_score=0.0,
            ocr_required=False,
            ocr_expected_coverage=0.0,
            asr_expected_value=0.5,
            structural_video_type="none",
        )


def _probe_structural_inner(
    sampled_frames: list[Any],
    visual_cut_count: int,
    visual_motion_density: float,
    has_speech: bool,
    has_music: bool,
    metadata_prior_confidence: float = 0.5,
) -> StructuralProbeResult:
    import cv2

    if not sampled_frames:
        return StructuralProbeResult(
            structural_score=0.0,
            list_likelihood=0.0,
            countdown_likelihood=0.0,
            overlay_text_density=0.0,
            ordinal_pattern_score=0.0,
            scene_repeat_score=0.0,
            ocr_required=False,
            ocr_expected_coverage=0.0,
            asr_expected_value=0.5,
            structural_video_type="none",
        )

    # 1. Overlay Text Density via MSER (fast CPU text region detection)
    mser = cv2.MSER_create()
    total_text_regions = 0
    frames_with_text = 0

    for frame in sampled_frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        regions, _ = mser.detectRegions(gray)
        # Filter for text-like bounding boxes
        text_like_boxes = 0
        for p in regions:
            x, y, w, h = cv2.boundingRect(p)
            if 0.1 < w / h < 10 and w > 15 and h > 15:
                text_like_boxes += 1
        
        # Scale down MSER raw regions to a more realistic "text block" count
        # MSER often finds individual characters/strokes.
        estimated_blocks = text_like_boxes // 5
        
        total_text_regions += estimated_blocks
        if estimated_blocks > 0:
            frames_with_text += 1

    overlay_text_density = total_text_regions / len(sampled_frames)
    ocr_expected_coverage = frames_with_text / len(sampled_frames)

    # 2. Ordinal Pattern Score (placeholder: without full OCR in Stage A,
    # we can't reliably read the text. We simulate this for now or rely
    # on metadata hints later. We keep it 0.0 unless we run lightweight OCR).
    # Since we can't run Tesseract on all frames here without blocking,
    # ordinal_pattern_score remains 0.0.
    ordinal_pattern_score = 0.0

    # 3. Scene Repeat Score (Histogram similarity across sampled frames)
    # Lists often have repeated layouts (e.g. title cards).
    similarities = []
    if len(sampled_frames) > 1:
        hists = []
        for frame in sampled_frames:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
            cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
            hists.append(hist)
            
        for i in range(len(hists) - 1):
            for j in range(i + 1, len(hists)):
                sim = cv2.compareHist(hists[i], hists[j], cv2.HISTCMP_CORREL)
                if sim > 0:
                    similarities.append(sim)
                    
    scene_repeat_score = sum(similarities) / len(similarities) if similarities else 0.0

    # 4. Compute composite scores
    # A list video typically has high text density, scene cuts, and some repeated structure.
    structural_score = 0.0
    
    # A. Graded Text Density (magnitude matters, not just presence)
    OVERLAY_DENSITY_EXTREME = 15.0  # TUNABLE: massive text wall
    if overlay_text_density > OVERLAY_DENSITY_EXTREME:
        structural_score += 0.5  # Almost crosses 0.55 on its own
    elif overlay_text_density > OVERLAY_DENSITY_HIGH:
        structural_score += 0.3

    # B. Scale-Invariant Motion (cuts per minute, not absolute cuts)
    MOTION_DENSITY_HIGH = 10.0  # TUNABLE: 10 cuts per minute
    if visual_motion_density > MOTION_DENSITY_HIGH:
        structural_score += 0.2

    # C. Scene Repetition
    if scene_repeat_score > SCENE_REPEAT_SIMILARITY_THRESHOLD:
        structural_score += 0.2
        
    # D. Metadata Corroboration (Bayesian Weak Prior)
    # If the title hints at a list (>0.5) AND we physically see text on screen,
    # let them corroborate each other to push over the threshold.
    if metadata_prior_confidence > 0.5 and overlay_text_density > OVERLAY_DENSITY_HIGH:
        structural_score += 0.15
        
    structural_score = min(structural_score, 1.0)
    
    # 5. Classify Video Type
    structural_video_type = "none"
    if structural_score >= STRUCTURAL_SCORE_THRESHOLD:
        if has_music and not has_speech and visual_motion_density > 10.0:
            structural_video_type = "compilation"
        elif overlay_text_density > OVERLAY_DENSITY_HIGH and visual_motion_density < 5.0:
            structural_video_type = "slideshow"
        else:
            structural_video_type = "list"
            
    list_likelihood = structural_score if structural_video_type in ("list", "ranking", "compilation") else 0.0
    countdown_likelihood = 0.0  # Would need OCR to detect decrementing numbers
    
    # 6. Determine if OCR is required
    ocr_required = structural_score >= STRUCTURAL_SCORE_THRESHOLD
    
    # 7. Expected ASR value
    asr_expected_value = 0.5
    if structural_video_type in ("list", "ranking", "compilation") and has_music:
        asr_expected_value = 0.2  # Likely lyrics, low value for taxonomy

    return StructuralProbeResult(
        structural_score=round(structural_score, 3),
        list_likelihood=round(list_likelihood, 3),
        countdown_likelihood=round(countdown_likelihood, 3),
        overlay_text_density=round(overlay_text_density, 3),
        ordinal_pattern_score=round(ordinal_pattern_score, 3),
        scene_repeat_score=round(scene_repeat_score, 3),
        ocr_required=ocr_required,
        ocr_expected_coverage=round(ocr_expected_coverage, 3),
        asr_expected_value=round(asr_expected_value, 3),
        structural_video_type=structural_video_type,
    )
