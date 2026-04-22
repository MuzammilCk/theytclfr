from ytclfr.alignment.normalizer import NormalizedEvidence

# Overlap window tolerance — TUNABLE
OVERLAP_TOLERANCE_SEC: float = 0.5  # TUNABLE

def _do_overlap(a: NormalizedEvidence, b: NormalizedEvidence) -> bool:
    """Check if two NormalizedEvidence items overlap temporally."""
    # Both are point-in-time
    if a.end_sec is None and b.end_sec is None:
        return abs(a.start_sec - b.start_sec) <= OVERLAP_TOLERANCE_SEC

    # A is range, B is point
    if a.end_sec is not None and b.end_sec is None:
        return a.start_sec <= b.start_sec <= a.end_sec

    # A is point, B is range
    if a.end_sec is None and b.end_sec is not None:
        return b.start_sec <= a.start_sec <= b.end_sec

    # Both are ranges
    if a.end_sec is not None and b.end_sec is not None:
        return max(a.start_sec, b.start_sec) <= min(a.end_sec, b.end_sec)

    return False

def detect_overlaps(
    evidence: list[NormalizedEvidence],
) -> list[tuple[NormalizedEvidence, NormalizedEvidence]]:
    """Detect temporal overlaps between NormalizedEvidence items."""
    overlaps = []
    n = len(evidence)
    for i in range(n):
        for j in range(i + 1, n):
            a = evidence[i]
            b = evidence[j]
            if _do_overlap(a, b):
                # Order by earlier start_sec
                if a.start_sec <= b.start_sec:
                    overlaps.append((a, b))
                else:
                    overlaps.append((b, a))

    # Return list of overlapping pairs, sorted by the earlier start_sec
    overlaps.sort(key=lambda pair: pair[0].start_sec)
    return overlaps

def resolve_overlaps(
    evidence: list[NormalizedEvidence],
) -> list[NormalizedEvidence]:
    """Resolve overlaps deterministically."""
    resolved_all: list[NormalizedEvidence] = []

    # Separate by source
    sources = set(e.source for e in evidence)
    for source in sources:
        source_evidence = [e for e in evidence if e.source == source]
        # Sort by start_sec
        source_evidence.sort(key=lambda e: e.start_sec)

        resolved: list[NormalizedEvidence] = []
        for item in source_evidence:
            if not resolved:
                resolved.append(item)
                continue

            # Check overlap with the last kept item
            while resolved and _do_overlap(resolved[-1], item):
                last = resolved[-1]
                if item.confidence > last.confidence:
                    # Item wins, pop last and check again
                    resolved.pop()
                elif item.confidence == last.confidence:
                    # Tie: keep earlier. 'last' is earlier since we sorted by start_sec.
                    # Item loses, so we stop checking.
                    item = last
                    break
                else:
                    # last has higher confidence, item loses.
                    item = last
                    break

            if not resolved or resolved[-1] != item:
                if item not in resolved:
                    resolved.append(item)

        resolved_all.extend(resolved)

    # Sort final result by start_sec
    resolved_all.sort(key=lambda e: (e.start_sec, e.source))
    return resolved_all
