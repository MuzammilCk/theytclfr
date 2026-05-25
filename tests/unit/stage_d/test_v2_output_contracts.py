import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from ytclfr.contracts.v2_output import (
    V2FinalOutput, TaxonomyResult, ExtractedItem,
)

def _load_golden() -> dict:
    p = (
        Path(__file__).parent.parent.parent
        / "fixtures" / "v2_final_output_golden.json"
    )
    return json.loads(p.read_text())

class TestV2OutputContracts:

    def test_golden_fixture_validates(self):
        """Golden fixture must validate into V2FinalOutput."""
        data = _load_golden()
        output = V2FinalOutput.model_validate(data)
        assert output.taxonomy.parent_category == "Education"
        assert output.taxonomy.groq_taxonomy_used is True
        assert len(output.items) == 2
        assert output.confidence["overall"] > 0.0

    def test_taxonomy_confidence_over_one_rejected(self):
        """TaxonomyResult confidence > 1.0 must raise."""
        with pytest.raises(ValidationError):
            TaxonomyResult(
                parent_category="Education",
                child_category="Tutorial",
                intent="Learn",
                confidence=1.5,
            )

    def test_extracted_item_valid_types(self):
        """All ExtractedItem item_type values must be accepted."""
        for itype in ["product","person","place","topic"]:
            item = ExtractedItem(
                name="Test", item_type=itype, confidence=0.8
            )
            assert item.item_type == itype

    def test_v2_output_empty_items_valid(self):
        """V2FinalOutput with empty items list is valid."""
        data = _load_golden()
        data["items"] = []
        output = V2FinalOutput.model_validate(data)
        assert output.items == []

    def test_confidence_dict_invalid_value_rejected(self):
        """confidence dict value > 1.0 must raise ValidationError."""
        data = _load_golden()
        data["confidence"]["overall"] = 1.5
        with pytest.raises(ValidationError):
            V2FinalOutput.model_validate(data)

    def test_taxonomy_result_frozen(self):
        """TaxonomyResult is frozen — mutation must raise."""
        t = TaxonomyResult(
            parent_category="Education",
            child_category="Tutorial",
            intent="Learn",
            confidence=0.9,
        )
        with pytest.raises(Exception):
            t.parent_category = "Sports"  # type: ignore
