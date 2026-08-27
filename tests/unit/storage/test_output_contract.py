import uuid
from datetime import datetime, timezone
from ytclfr.contracts.output import FinalOutput, ScriptSegment

def test_final_output_contract():
    job_id = uuid.uuid4()
    item = ScriptSegment(timestamp=0.0, end_timestamp=1.0, text="hello", confidence=0.9)
    
    output = FinalOutput(
        job_id=job_id,
        content_type="script",
        video_metadata={},
        script=[item],
        confidence=0.9,
        provenance=[{"source": "asr"}],
        processed_at=datetime.now(timezone.utc),
        processing_duration_seconds=10.0
    )
    
    dumped = output.model_dump(mode="json")
    validated = FinalOutput.model_validate(dumped)
    
    assert validated.job_id == job_id
    assert validated.content_type == "script"
    assert validated.confidence == 0.9
    assert len(validated.script) == 1 # type: ignore
    assert isinstance(validated.script[0], ScriptSegment) # type: ignore
