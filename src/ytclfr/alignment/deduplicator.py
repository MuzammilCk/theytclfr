import difflib

from ytclfr.alignment.normalizer import NormalizedEvidence

# Max time delta for cross-modal duplicate detection — TUNABLE
MERGE_WINDOW_MS: int = 2000  # TUNABLE (milliseconds)

# Minimum text similarity ratio for merge — TUNABLE
MERGE_SIMILARITY_THRESHOLD: float = 0.6  # TUNABLE

def compute_text_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two texts."""
    return difflib.SequenceMatcher(
        None,
        a.strip().lower(),
        b.strip().lower()
    ).ratio()

def deduplicate_cross_modal(
    evidence: list[NormalizedEvidence],
) -> list[NormalizedEvidence]:
    """Detect and merge duplicate evidence across modalities."""
    asr_items = [e for e in evidence if e.source == "asr"]
    ocr_items = [e for e in evidence if e.source == "ocr"]

    consumed_ids: set[str] = set()
    merged_items: list[NormalizedEvidence] = []

    for ocr in ocr_items:
        if ocr.segment_id in consumed_ids:
            continue

        for asr in asr_items:
            if asr.segment_id in consumed_ids:
                continue

            if abs(asr.start_sec - ocr.start_sec) * 1000 <= MERGE_WINDOW_MS:
                sim = compute_text_similarity(asr.text, ocr.text)
                if sim >= MERGE_SIMILARITY_THRESHOLD:
                    merged_item = NormalizedEvidence(
                        start_sec=min(asr.start_sec, ocr.start_sec),
                        end_sec=asr.end_sec,
                        source="merged",
                        text=asr.text if len(asr.text) >= len(ocr.text) else ocr.text,
                        confidence=max(asr.confidence, ocr.confidence),
                        segment_id=f"{asr.segment_id},{ocr.segment_id}"
                    )
                    merged_items.append(merged_item)
                    consumed_ids.add(ocr.segment_id)
                    consumed_ids.add(asr.segment_id)
                    break

    unconsumed_items = [e for e in evidence if e.segment_id not in consumed_ids]

    result = merged_items + unconsumed_items
    result.sort(key=lambda e: (e.start_sec, e.source))
    return result
