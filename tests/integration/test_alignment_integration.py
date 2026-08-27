import json
import uuid
from pathlib import Path

from ytclfr.alignment.engine import align
from ytclfr.contracts.alignment import AlignedTimeline


def test_full_extractor_output_to_aligned_segments():
    # Load fixtures
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    asr_path = fixtures_dir / "extractor_result_asr.json"
    ocr_path = fixtures_dir / "extractor_result_ocr.json"

    with open(asr_path, encoding="utf-8") as f:
        asr_result = json.load(f)

    with open(ocr_path, encoding="utf-8") as f:
        ocr_result = json.load(f)

    extractor_results = [asr_result, ocr_result]
    job_id = uuid.uuid4()

    # Run alignment
    timeline = align(job_id, extractor_results)

    # Assertions
    assert isinstance(timeline, AlignedTimeline)
    assert timeline.total_segments > 0
    assert len(timeline.segments) == timeline.total_segments

    for segment in timeline.segments:
        assert segment.source in ("asr", "ocr", "merged")

    # Validate against schema
    AlignedTimeline.model_validate(timeline.model_dump())
