import json
from pathlib import Path
from datetime import timezone

import pytest
from pydantic import ValidationError

from ytclfr.contracts.evidence import (
    EvidenceGraph, ExtractedEntity, FusedSegment,
)


def _load_golden() -> dict:
    p = (
        Path(__file__).parent.parent.parent
        / "fixtures" / "evidence_graph_golden.json"
    )
    return json.loads(p.read_text())


class TestEvidenceContracts:

    def test_golden_fixture_validates(self):
        """Golden fixture must validate into EvidenceGraph."""
        data = _load_golden()
        graph = EvidenceGraph.model_validate(data)
        assert graph.total_segments == 2
        assert len(graph.entities) == 2
        assert graph.groq_reasoning_used is True
        assert graph.dominant_subject is not None

    def test_confidence_over_one_rejected(self):
        """confidence > 1.0 must raise ValidationError."""
        data = _load_golden()
        data["confidence"] = 1.5
        with pytest.raises(ValidationError):
            EvidenceGraph.model_validate(data)

    def test_confidence_negative_rejected(self):
        """confidence < 0.0 must raise ValidationError."""
        data = _load_golden()
        data["confidence"] = -0.1
        with pytest.raises(ValidationError):
            EvidenceGraph.model_validate(data)

    def test_fused_segment_valid_sources(self):
        """All valid FusedSegment source values are accepted."""
        for source in ["asr", "ocr", "merged", "audio"]:
            seg = FusedSegment(
                timestamp=0.0, text="test",
                source=source, confidence=0.9,
            )
            assert seg.source == source

    def test_extracted_entity_valid_types(self):
        """All valid ExtractedEntity entity_type values are accepted."""
        for etype in ["product","person","place","topic","unknown"]:
            e = ExtractedEntity(
                name="Test", entity_type=etype,
                mentioned_at=[0.0], confidence=0.5,
            )
            assert e.entity_type == etype

    def test_extracted_entity_invalid_type_rejected(self):
        """Invalid entity_type must raise ValidationError."""
        with pytest.raises(ValidationError):
            ExtractedEntity(
                name="Test", entity_type="celebrity",
                mentioned_at=[0.0], confidence=0.5,
            )

    def test_evidence_graph_empty_entities_valid(self):
        """EvidenceGraph with empty entities and segments is valid."""
        data = _load_golden()
        data["segments"] = []
        data["entities"] = []
        data["total_segments"] = 0
        graph = EvidenceGraph.model_validate(data)
        assert graph.total_segments == 0
