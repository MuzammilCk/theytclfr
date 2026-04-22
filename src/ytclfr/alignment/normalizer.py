from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedEvidence:
    """Single piece of evidence on the timeline."""
    start_sec: float          # seconds from video start
    end_sec: float | None     # None for point-in-time (OCR)
    source: str               # "asr", "ocr", "audio"
    text: str
    confidence: float         # 0.0–1.0
    segment_id: str           # unique ID for tracing: "{source}-{index}"

def normalize_extractor_results(
    extractor_results: list[dict[str, Any]],
) -> list[NormalizedEvidence]:
    """Convert all extractor outputs into a uniform internal representation."""
    evidence_list: list[NormalizedEvidence] = []

    for result in extractor_results:
        if result.get("error") is not None:
            continue

        extractor_type = result.get("extractor_type")
        if extractor_type not in ("asr", "ocr"):
            continue

        segments = result.get("segments", [])
        for i, segment in enumerate(segments):
            if extractor_type == "asr":
                evidence = NormalizedEvidence(
                    start_sec=segment["start_time"],
                    end_sec=segment["end_time"],
                    source="asr",
                    text=segment["text"],
                    confidence=segment["confidence"],
                    segment_id=f"asr-{i}"
                )
                evidence_list.append(evidence)
            elif extractor_type == "ocr":
                evidence = NormalizedEvidence(
                    start_sec=segment["frame_timestamp"],
                    end_sec=None,
                    source="ocr",
                    text=segment["text"],
                    confidence=segment["confidence"],
                    segment_id=f"ocr-{i}"
                )
                evidence_list.append(evidence)

    # Sort output by start_sec ascending. Ties broken by source ("asr" before "ocr")
    evidence_list.sort(key=lambda e: (e.start_sec, e.source))
    return evidence_list
