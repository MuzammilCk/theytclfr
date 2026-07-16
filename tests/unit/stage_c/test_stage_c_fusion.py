"""Regression tests for v3_run_evidence_fusion (Stage C orchestrator).

Covers the entity-grounding fix: entities must no longer be hardcoded
to an empty list. A deterministic heuristic baseline should always be
computed, and Groq's refined entities should only replace it when
Groq actually succeeds and returns something.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from ytclfr.db.models.job import Job
from ytclfr.db.models.v3.v3_extractor_bundles import V3ExtractorBundleORM
from ytclfr.db.models.v3.v3_evidence_graphs import V3EvidenceGraphORM
from ytclfr.contracts.v3.manifest import SignalManifest
from ytclfr.fusion.v3_groq_reasoner import V3GroqReasoningResult
from ytclfr.tasks.v3.stage_c_fusion import v3_run_evidence_fusion


def _make_manifest(**overrides) -> SignalManifest:
    """Build a minimal valid V3 SignalManifest with sensible defaults."""
    defaults = dict(
        job_id=uuid4(),
        audio_type="speech_only",
        has_speech=True,
        has_music=False,
        has_burned_in_text=False,
        has_subtitle_track=False,
        has_faces=False,
        motion_density=2.0,
        motion_score=0.3,
        aspect_ratio="16:9",
        content_format="live_action",
        scene_cut_count=5,
        duration_seconds=120.0,
        probing_confidence=0.8,
        structural_video_type="none",
    )
    defaults.update(overrides)
    return SignalManifest(**defaults)


def _make_mock_db(job, bundle, existing_evidence_graph=None):
    """Route db.query(Model) to the right canned result per model."""
    mock_db = MagicMock()

    def query_side_effect(model):
        m = MagicMock()
        if model is Job:
            m.filter.return_value.first.return_value = job
        elif model is V3ExtractorBundleORM:
            m.filter.return_value.first.return_value = bundle
        elif model is V3EvidenceGraphORM:
            m.filter.return_value.first.return_value = existing_evidence_graph
        return m

    mock_db.query.side_effect = query_side_effect
    return mock_db


def _make_bundle():
    bundle = MagicMock()
    # Repeated so the heuristic extractor's mention-count confidence
    # scaling produces a comfortably non-trivial score.
    text = "Welcome to the Python Tutorial today"
    bundle.asr_segments_json = [
        {"start_time": float(i), "end_time": float(i) + 2.0, "text": text, "confidence": 0.9}
        for i in range(6)
    ]
    bundle.ocr_segments_json = []
    bundle.asr_metrics_json = None
    return bundle


def _run(job_id, job, bundle, manifest, groq_result):
    mock_db = _make_mock_db(job, bundle, existing_evidence_graph=None)
    added_objects = []
    mock_db.add.side_effect = lambda obj: added_objects.append(obj)

    with (
        patch("ytclfr.tasks.v3.stage_c_fusion.db_session") as mock_db_session,
        patch("ytclfr.tasks.v3.stage_c_fusion.SignalManifestStore") as mock_store_cls,
        patch("ytclfr.tasks.v3.stage_c_fusion.v3_reason_over_evidence") as mock_reason,
        patch("ytclfr.tasks.v3.stage_c_fusion.v3_run_taxonomy_mapping") as mock_stage_d,
    ):
        mock_db_session.return_value.__enter__.return_value = mock_db
        mock_store_cls.return_value.get_by_job_id.return_value = manifest
        mock_reason.return_value = groq_result

        result = v3_run_evidence_fusion.apply(args=[str(job_id)])
        value = result.get()

    assert value["status"] == "fused"
    assert mock_stage_d.delay.called
    assert len(added_objects) == 1
    return added_objects[0]


def test_groq_failure_falls_back_to_heuristic_entities():
    """When Groq is unavailable, entities must NOT be an empty list —
    the heuristic baseline should be persisted instead."""
    job_id = uuid4()
    job = MagicMock(id=job_id)
    bundle = _make_bundle()
    manifest = _make_manifest(job_id=job_id)

    groq_failure = V3GroqReasoningResult(
        dominant_subject=None,
        summary=None,
        refined_entities=[],
        scene_boundaries=[0.0],
        reasoning_used=False,
    )

    saved_graph = _run(job_id, job, bundle, manifest, groq_failure)

    entities = saved_graph.entities_json["entities"]
    assert entities, "entities must not be empty when Groq fails"
    assert any(e["name"] == "Python Tutorial" for e in entities)
    assert saved_graph.groq_reasoning_used is False


def test_groq_success_uses_refined_entities():
    """When Groq succeeds and returns entities, its refined set should
    be used instead of the raw heuristic baseline."""
    job_id = uuid4()
    job = MagicMock(id=job_id)
    bundle = _make_bundle()
    manifest = _make_manifest(job_id=job_id)

    groq_success = V3GroqReasoningResult(
        dominant_subject="A Python programming tutorial",
        summary="A tutorial teaching Python basics.",
        refined_entities=[
            {
                "name": "Python Tutorial",
                "entity_type": "topic",
                "mentioned_at": [0.0, 2.0],
                "confidence": 0.95,
            }
        ],
        scene_boundaries=[0.0],
        reasoning_used=True,
    )

    saved_graph = _run(job_id, job, bundle, manifest, groq_success)

    entities = saved_graph.entities_json["entities"]
    assert entities == groq_success.refined_entities
    assert saved_graph.dominant_subject == "A Python programming tutorial"
    assert saved_graph.groq_reasoning_used is True


def test_groq_success_but_empty_entities_falls_back_to_heuristics():
    """Groq can 'succeed' (valid JSON) but return zero entities — that
    should still fall back to the heuristic baseline rather than
    persisting an empty list."""
    job_id = uuid4()
    job = MagicMock(id=job_id)
    bundle = _make_bundle()
    manifest = _make_manifest(job_id=job_id)

    groq_empty = V3GroqReasoningResult(
        dominant_subject="Something",
        summary="A short video.",
        refined_entities=[],
        scene_boundaries=[0.0],
        reasoning_used=True,
    )

    saved_graph = _run(job_id, job, bundle, manifest, groq_empty)

    entities = saved_graph.entities_json["entities"]
    assert entities, "should fall back to heuristics when Groq returns nothing"
    assert any(e["name"] == "Python Tutorial" for e in entities)
