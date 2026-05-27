import logging
from dataclasses import dataclass
import json

from ytclfr.contracts.v3.evidence import EvidenceGraph
from ytclfr.core.config import Settings

logger = logging.getLogger(__name__)

# ── TUNABLE CONSTANTS ──────────────────────────────────────

GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TEMPERATURE: float = 0.1
GROQ_MAX_TOKENS: int = 2000
MAX_SCENE_BOUNDARIES: int = 20


@dataclass
class V3GroqReasoningResult:
    """Result of Groq semantic reasoning over V3 EvidenceGraph."""
    dominant_subject: str | None
    summary: str | None
    refined_entities: list[dict]
    scene_boundaries: list[float]
    reasoning_used: bool = True


_GROQ_FAILURE_RESULT = V3GroqReasoningResult(
    dominant_subject=None,
    summary=None,
    refined_entities=[],
    scene_boundaries=[0.0],
    reasoning_used=False,
)


def v3_reason_over_evidence(
    evidence_graph: EvidenceGraph,
    settings: Settings,
) -> V3GroqReasoningResult:
    """Call Groq to reason semantically over the structured EvidenceGraph."""
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY is not configured — skipping Groq reasoning")
        return _GROQ_FAILURE_RESULT

    try:
        prompt = _build_prompt(evidence_graph)
        raw_response = _call_groq_api(prompt, settings)
        return _parse_response(raw_response)
    except Exception as exc:
        logger.warning(
            "Groq reasoning failed — pipeline continues without it: %s",
            exc,
        )
        return _GROQ_FAILURE_RESULT


def _build_prompt(evidence_graph: EvidenceGraph) -> str:
    """Build the Groq prompt from the structured JSON EvidenceGraph."""
    
    # We serialize a simplified version of the evidence graph for the LLM
    # to avoid blowing up the context window.
    # We take at most 300 segments.
    segments_subset = [s.model_dump(mode="json") for s in evidence_graph.segments[:300]]
    entities_subset = [e.model_dump(mode="json") for e in evidence_graph.entities]
    
    evidence_payload = {
        "structural_video_type": evidence_graph.structural_video_type,
        "primary_evidence_modality": evidence_graph.primary_evidence_modality,
        "entities_extracted_by_heuristics": entities_subset,
        "timeline_segments": segments_subset,
    }
    
    evidence_json = json.dumps(evidence_payload, indent=2)

    return (
        "Analyze the following JSON EvidenceGraph of a video and respond ONLY with a "
        "valid JSON object. No markdown, no backticks.\n\n"
        f"EVIDENCE_GRAPH:\n{evidence_json}\n\n"
        "Respond with this exact JSON structure:\n"
        '{\n'
        '  "dominant_subject": "what this video is primarily about in one sentence",\n'
        '  "summary": "2-3 sentence summary of the video content",\n'
        '  "entities": [\n'
        '    {"name": "entity name", "type": "product|person|place|topic", "timestamps": [0.0, 12.5]}\n'
        '  ],\n'
        '  "scene_boundaries": [0.0, 45.2, 120.0]\n'
        '}\n\n'
        "scene_boundaries: timestamps (seconds) where major topic "
        "shifts occur. Always include 0.0."
    )


def _call_groq_api(prompt: str, settings: Settings) -> str:
    """Make the Groq API call. Returns raw response string."""
    import httpx

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": GROQ_TEMPERATURE,
        "max_tokens": GROQ_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(
        timeout=settings.llm_request_timeout_seconds
    ) as client:
        response = client.post(
            GROQ_API_URL, headers=headers, json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _parse_response(raw_json: str) -> V3GroqReasoningResult:
    """Parse Groq's JSON response into V3GroqReasoningResult."""
    data = json.loads(raw_json)

    raw_entities = data.get("entities", [])
    refined: list[dict] = []
    for e in raw_entities:
        if isinstance(e, dict) and "name" in e and "type" in e:
            refined.append({
                "name": str(e["name"]),
                "type": str(e.get("type", "unknown")),
                "timestamps": [
                    float(t)
                    for t in e.get("timestamps", [])
                    if isinstance(t, (int, float))
                ],
            })

    raw_boundaries = data.get("scene_boundaries", [0.0])
    boundaries = [
        float(t)
        for t in raw_boundaries
        if isinstance(t, (int, float))
    ][:MAX_SCENE_BOUNDARIES]
    if not boundaries:
        boundaries = [0.0]

    subject = data.get("dominant_subject") or None
    summary = data.get("summary") or None

    return V3GroqReasoningResult(
        dominant_subject=subject,
        summary=summary,
        refined_entities=refined,
        scene_boundaries=boundaries,
        reasoning_used=True,
    )
