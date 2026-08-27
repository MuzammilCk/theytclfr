from typing import Literal, cast

from ytclfr.alignment.normalizer import NormalizedEvidence
from ytclfr.contracts.alignment import AlignedSegment

# Gap threshold — TUNABLE
GAP_THRESHOLD_SEC: float = 2.0  # TUNABLE


def create_segments(
    evidence: list[NormalizedEvidence],
) -> list[AlignedSegment]:
    """Convert NormalizedEvidence into AlignedSegment objects."""
    segments = []
    for e in evidence:
        segment = AlignedSegment(
            timestamp=e.start_sec,
            end_timestamp=e.end_sec,
            source=cast(Literal["asr", "ocr", "merged"], e.source),
            text=e.text,
            confidence=e.confidence,
            original_segment_ids=e.segment_id.split(","),
        )
        segments.append(segment)

    segments.sort(key=lambda s: s.timestamp)
    return segments


def detect_gaps(
    segments: list[AlignedSegment],
) -> bool:
    """Detect if there are significant temporal gaps between segments."""
    if not segments:
        return False

    for i in range(len(segments) - 1):
        current = segments[i]
        next_seg = segments[i + 1]

        current_end = (
            current.end_timestamp
            if current.end_timestamp is not None
            else current.timestamp
        )
        if next_seg.timestamp - current_end > GAP_THRESHOLD_SEC:
            return True

    return False
