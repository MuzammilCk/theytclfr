"""Groq-powered semantic reasoning over aligned evidence.

Pure function — no Celery, no DB.
Calls Groq to produce dominant subject, summary, refined
entities, and scene boundaries from the aligned transcript.

All failures degrade gracefully: returns GroqReasoningResult
with reasoning_used=False. The pipeline never blocks on Groq.
"""

import logging
from dataclasses import dataclass

from ytclfr.contracts.alignment import AlignedSegment
from ytclfr.contracts.evidence import ExtractedEntity
from ytclfr.core.config import Settings

logger = logging.getLogger(__name__)

# ── TUNABLE CONSTANTS ──────────────────────────────────────

GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TEMPERATURE: float = 0.1
GROQ_MAX_TOKENS: int = 2000
MAX_TRANSCRIPT_CHARS: int = 8000   # cap prompt to stay within Groq context
MAX_ENTITY_HINTS: int = 10         # send at most this many candidate entities
MAX_SCENE_BOUNDARIES: int = 20     # cap Groq-returned boundary list


@dataclass
class GroqReasoningResult:
    """Result of Groq semantic reasoning over aligned evidence."""
    dominant_subject: str | None
    summary: str | None
    refined_entities: list[dict]  # raw dicts from Groq JSON
    scene_boundaries: list[float]
    reasoning_used: bool = True


_GROQ_FAILURE_RESULT = GroqReasoningResult(
    dominant_subject=None,
    summary=None,
    refined_entities=[],
    scene_boundaries=[0.0],
    reasoning_used=False,
)


def reason_over_evidence(
    segments: list[AlignedSegment],
    entity_hints: list[ExtractedEntity],
    settings: Settings,
) -> GroqReasoningResult:
    """Call Groq to reason semantically over the aligned timeline.

    If settings.groq_api_key is empty, returns the failure default
    immediately without making a network call.

    Never raises — all exceptions produce _GROQ_FAILURE_RESULT.

    Args:
        segments: Aligned timeline from align().
        entity_hints: Candidate entities from entity_extractor.
        settings: App settings (groq_api_key, groq_model, etc.)

    Returns:
        GroqReasoningResult. reasoning_used=False if Groq failed.
    """
    if not settings.groq_api_key:
        logger.warning(
            "GROQ_API_KEY is not configured — skipping Groq reasoning"
        )
        return _GROQ_FAILURE_RESULT

    try:
        prompt = _build_prompt(segments, entity_hints)
        raw_response = _call_groq_api(prompt, settings)
        return _parse_response(raw_response)
    except Exception as exc:
        logger.warning(
            "Groq reasoning failed — pipeline continues without it: %s",
            exc,
        )
        return _GROQ_FAILURE_RESULT


def _build_prompt(
    segments: list[AlignedSegment],
    entity_hints: list[ExtractedEntity],
) -> str:
    """Build the Groq prompt from aligned segments + entity hints."""
    lines: list[str] = []
    for seg in segments:
        lines.append(f"[{seg.timestamp:.1f}s] {seg.text}")
    transcript = "\n".join(lines)[:MAX_TRANSCRIPT_CHARS]

    hint_str = (
        ", ".join(e.name for e in entity_hints[:MAX_ENTITY_HINTS])
        if entity_hints
        else "none detected"
    )

    return (
        "Analyze this video transcript and respond ONLY with a "
        "valid JSON object. No markdown, no backticks.\n\n"
        f"TRANSCRIPT (with timestamps):\n{transcript}\n\n"
        f"CANDIDATE ENTITIES DETECTED: {hint_str}\n\n"
        "Respond with this exact JSON structure:\n"
        '{\n'
        '  "dominant_subject": "what this video is primarily about'
        ' in one sentence",\n'
        '  "summary": "2-3 sentence summary of the video content",\n'
        '  "entities": [\n'
        '    {"name": "entity name", "type": '
        '"product|person|place|topic", "timestamps": [0.0, 12.5]}\n'
        '  ],\n'
        '  "scene_boundaries": [0.0, 45.2, 120.0]\n'
        '}\n\n'
        "scene_boundaries: timestamps (seconds) where major topic "
        "shifts occur. Always include 0.0."
    )


def _call_groq_api(prompt: str, settings: Settings) -> str:
    """Make the Groq API call. Returns raw response string.

    Raises on any HTTP or network error — caller handles.
    """
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


def _parse_response(raw_json: str) -> GroqReasoningResult:
    """Parse Groq's JSON response into GroqReasoningResult.

    Raises json.JSONDecodeError or KeyError on malformed response.
    Caller handles and falls back to _GROQ_FAILURE_RESULT.
    """
    import json

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

    return GroqReasoningResult(
        dominant_subject=subject,
        summary=summary,
        refined_entities=refined,
        scene_boundaries=boundaries,
        reasoning_used=True,
    )
