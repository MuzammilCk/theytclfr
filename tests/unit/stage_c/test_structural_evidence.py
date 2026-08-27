"""Tests validating the structural golden fixture against EvidenceGraph."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ytclfr.contracts.evidence import EvidenceGraph


def _load_structural_golden() -> dict:
    p = (
        Path(__file__).parent.parent.parent
        / "fixtures" / "evidence_graph_structural_golden.json"
    )
    return json.loads(p.read_text())


class TestStructuralEvidenceGraph:

    def test_structural_golden_validates(self):
        """Structural golden fixture must validate into EvidenceGraph."""
        data = _load_structural_golden()
        graph = EvidenceGraph.model_validate(data)
        assert graph.total_segments == 5
        assert graph.structural_video_type == "ranking"
        assert graph.primary_evidence_modality == "ocr"
        assert graph.conflict_count == 1
        assert len(graph.conflict_details) == 1
        assert graph.conflict_details[0]["resolution"] == "ocr_wins"

    def test_structural_golden_entities_are_products(self):
        """Entities in a ranking video should be products."""
        data = _load_structural_golden()
        graph = EvidenceGraph.model_validate(data)
        for entity in graph.entities:
            assert entity.entity_type == "product"

    def test_structural_golden_modality_coverage(self):
        """modality_coverage should have both asr and ocr keys."""
        data = _load_structural_golden()
        graph = EvidenceGraph.model_validate(data)
        assert "asr" in graph.modality_coverage
        assert "ocr" in graph.modality_coverage
        assert graph.modality_coverage["ocr"] > graph.modality_coverage["asr"]

    def test_structural_golden_evidence_priority_notes(self):
        """Evidence priority notes should reference OCR prioritization."""
        data = _load_structural_golden()
        graph = EvidenceGraph.model_validate(data)
        assert len(graph.evidence_priority_notes) >= 1
        assert any("OCR prioritized" in note for note in graph.evidence_priority_notes)

    def test_structural_golden_rejects_invalid_structural_type(self):
        """structural_video_type must be a string — invalid confidence fails."""
        data = _load_structural_golden()
        data["confidence"] = 2.0  # invalid
        with pytest.raises(ValidationError):
            EvidenceGraph.model_validate(data)
