from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ytclfr.alignment.deduplicator import deduplicate_cross_modal
from ytclfr.alignment.normalizer import normalize_extractor_results
from ytclfr.alignment.overlap import resolve_overlaps
from ytclfr.alignment.segmenter import create_segments, detect_gaps
from ytclfr.contracts.alignment import AlignedTimeline


def align(
    job_id: UUID,
    extractor_results: list[dict[str, Any]],
) -> AlignedTimeline:
    """Orchestrate the full temporal alignment pipeline."""
    # 1. Normalize timestamps
    evidence = normalize_extractor_results(extractor_results)

    if not evidence:
        return AlignedTimeline(
            job_id=job_id,
            segments=[],
            total_segments=0,
            has_gaps=False,
            aligned_at=datetime.now(UTC),
        )

    # 2. Resolve overlaps deterministically
    resolved = resolve_overlaps(evidence)

    # 3. Deduplicate across modalities
    deduplicated = deduplicate_cross_modal(resolved)

    # 4. Create aligned segments
    segments = create_segments(deduplicated)

    # 5. Detect gaps
    has_gaps = detect_gaps(segments)

    # 6. Return AlignedTimeline
    return AlignedTimeline(
        job_id=job_id,
        segments=segments,
        total_segments=len(segments),
        has_gaps=has_gaps,
        aligned_at=datetime.now(UTC),
    )
