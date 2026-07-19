import logging
import time
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
GROQ_MAX_ATTEMPTS: int = 2
GROQ_RETRY_BACKOFF_SECONDS: float = 1.5
_VALID_ENTITY_TYPES: frozenset[str] = frozenset({
    "product", "person", "place", "topic", "unknown"
})


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

    prompt = _build_prompt(evidence_graph)
    last_exc: Exception | None = None
    for attempt in range(1, GROQ_MAX_ATTEMPTS + 1):
        try:
            raw_response = _call_groq_api(prompt, settings)
            return _parse_response(raw_response)
        except Exception as exc:
            last_exc = exc
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in (401, 403):
                break  # bad/expired key — retrying won't help
            if attempt < GROQ_MAX_ATTEMPTS:
                logger.warning(
                    "Groq reasoning attempt %d/%d failed, retrying: %s",
                    attempt, GROQ_MAX_ATTEMPTS, exc,
                )
                time.sleep(GROQ_RETRY_BACKOFF_SECONDS)

    logger.warning(
        "Groq reasoning failed after %d attempt(s) — pipeline continues without it: %s",
        GROQ_MAX_ATTEMPTS, last_exc,
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

    structural_hint = ""
    if evidence_graph.structural_video_type in ("list", "ranking", "countdown"):
        structural_hint = (
            "\n\nStructural signal: this video was detected as a "
            f"'{evidence_graph.structural_video_type}' — most likely a ranked or "
            "numbered list (e.g. \"Top 25 Movies\"). Expect MULTIPLE distinct "
            "ranked items rather than a single overall topic. Extract each "
            "individual item you can identify (e.g. each movie/product/place "
            "named) as its own entity, not just the general subject of the video."
        )

    return (
        "Analyze the following JSON EvidenceGraph of a video and respond ONLY with a "
        "valid JSON object. No markdown, no backticks.\n\n"
        f"EVIDENCE_GRAPH:\n{evidence_json}"
        f"{structural_hint}\n\n"
        "entities_extracted_by_heuristics are candidate entities already found by "
        "regex heuristics — reuse and correctly re-type the real ones, drop any that "
        "are clearly not meaningful entities, and add any genuine entities the "
        "heuristics missed.\n\n"
        "Respond with this exact JSON structure:\n"
        '{\n'
        '  "dominant_subject": "what this video is primarily about in one sentence",\n'
        '  "summary": "2-3 sentence summary of the video content",\n'
        '  "entities": [\n'
        '    {"name": "entity name", "entity_type": "product|person|place|topic", '
        '"mentioned_at": [0.0, 12.5], "confidence": 0.8}\n'
        '  ],\n'
        '  "scene_boundaries": [0.0, 45.2, 120.0]\n'
        '}\n\n'
        "confidence: your confidence (0.0-1.0) that this entity and its type are "
        "correct. scene_boundaries: timestamps (seconds) where major topic shifts "
        "occur. Always include 0.0."
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
        if not isinstance(e, dict) or "name" not in e:
            continue

        # Prefer the contract's real field names; fall back to the old
        # ones defensively in case the model doesn't follow the prompt
        # exactly — LLM output isn't perfectly deterministic even at
        # low temperature.
        entity_type = str(e.get("entity_type", e.get("type", "unknown")))
        if entity_type not in _VALID_ENTITY_TYPES:
            entity_type = "unknown"

        try:
            confidence = float(e.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.7

        raw_timestamps = e.get("mentioned_at", e.get("timestamps", []))
        refined.append({
            "name": str(e["name"]),
            "entity_type": entity_type,
            "mentioned_at": [
                float(t) for t in raw_timestamps if isinstance(t, (int, float))
            ],
            "confidence": confidence,
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
