"""Groq-powered taxonomy classification for Stage D.

Pure function — no Celery, no DB.
Accepts EvidenceGraph fields and returns TaxonomyResult.
Degrades gracefully: if Groq fails, the rule-based resolver
in intent_resolver.py provides a fallback TaxonomyResult.

Never raises to its caller.
"""
import logging
import time
from dataclasses import dataclass

from ytclfr.core.config import Settings
from ytclfr.taxonomy.intent_resolver import TaxonomyFallback

logger = logging.getLogger(__name__)

# ── TUNABLE CONSTANTS ──────────────────────────────────────

GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TAXONOMY_TEMPERATURE: float = 0.1
GROQ_TAXONOMY_MAX_TOKENS: int = 500
MAX_ENTITIES_IN_PROMPT: int = 8
MAX_SUMMARY_CHARS: int = 500
GROQ_MAX_ATTEMPTS: int = 2
GROQ_RETRY_BACKOFF_SECONDS: float = 1.5

VALID_PARENT_CATEGORIES: frozenset[str] = frozenset({
    "Education", "Shopping", "Sports", "Music",
    "Film", "Technology", "Food", "Health", "News", "Other",
})

# ── Output dataclass ───────────────────────────────────────

@dataclass
class GroqTaxonomyResult:
    """Raw parsed result from the Groq taxonomy call."""
    parent_category: str
    child_category: str
    intent: str
    confidence: float
    fallback_notes: list[str]
    groq_used: bool = True

# ── Public function ─────────────────────────────────────────

def classify_taxonomy(
    dominant_subject: str | None,
    groq_summary: str | None,
    entities: list[dict[str, str]],  # [{"name": str, "type": str}]
    has_speech: bool,
    has_music: bool,
    settings: Settings,
    structural_video_type: str = "none",
) -> GroqTaxonomyResult:
    """Classify video taxonomy using Groq. Degrades gracefully.

    Never raises — any failure returns a fallback result
    with groq_used=False.

    Args:
        dominant_subject: From EvidenceGraph.dominant_subject.
        groq_summary: From EvidenceGraph.groq_summary.
        entities: Simplified entity dicts from EvidenceGraph.
        has_speech: From SignalManifest (via EvidenceGraph context).
        has_music: From SignalManifest (via EvidenceGraph context).
        settings: App settings with groq_api_key.

    Returns:
        GroqTaxonomyResult. groq_used=False if Groq unavailable.
    """
    if not settings.groq_api_key:
        logger.warning(
            "GROQ_API_KEY not configured — using rule-based taxonomy"
        )
        fallback = _make_fallback_result(
            dominant_subject, has_speech, has_music, structural_video_type,
            note="Groq API key not configured"
        )
        return GroqTaxonomyResult(
            parent_category=fallback.parent_category,
            child_category=fallback.child_category,
            intent=fallback.intent,
            confidence=fallback.confidence,
            fallback_notes=fallback.fallback_notes,
            groq_used=False,
        )

    prompt = _build_taxonomy_prompt(
        dominant_subject, groq_summary, entities, structural_video_type
    )
    last_exc: Exception | None = None
    for attempt in range(1, GROQ_MAX_ATTEMPTS + 1):
        try:
            raw = _call_groq(prompt, settings)
            return _parse_taxonomy_response(raw)
        except Exception as exc:
            last_exc = exc
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in (401, 403):
                break  # bad/expired key — retrying won't help
            if attempt < GROQ_MAX_ATTEMPTS:
                logger.warning(
                    "Groq taxonomy attempt %d/%d failed, retrying: %s",
                    attempt, GROQ_MAX_ATTEMPTS, exc,
                )
                time.sleep(GROQ_RETRY_BACKOFF_SECONDS)

    logger.warning(
        "Groq taxonomy classification failed after %d attempt(s): %s. "
        "Using rule-based fallback.",
        GROQ_MAX_ATTEMPTS, last_exc,
    )
    fallback = _make_fallback_result(
        dominant_subject, has_speech, has_music, structural_video_type,
        note=f"Groq failed: {last_exc}"
    )
    return GroqTaxonomyResult(
        parent_category=fallback.parent_category,
        child_category=fallback.child_category,
        intent=fallback.intent,
        confidence=fallback.confidence,
        fallback_notes=fallback.fallback_notes,
        groq_used=False,
    )

# ── Private helpers ─────────────────────────────────────────

def _build_taxonomy_prompt(
    dominant_subject: str | None,
    groq_summary: str | None,
    entities: list[dict[str, str]],
    structural_video_type: str,
) -> str:
    subject_str = (dominant_subject or "unknown")[:200]
    summary_str = (groq_summary or "No summary available")[
        :MAX_SUMMARY_CHARS
    ]
    entity_str = ", ".join(
        e.get("name", "") for e in entities[:MAX_ENTITIES_IN_PROMPT]
    ) or "none"

    # For list/ranking/countdown/compilation formats, a handful of
    # visible entities is a red flag, not a complete picture: these
    # videos typically name many items (e.g. "Top 25 ..."), so a small
    # entity count usually means upstream extraction (e.g. OCR) missed
    # most of the on-screen content — it is NOT evidence that the video
    # is narrowly about whatever those few entities have in common.
    # Previously this was only a soft "factor this heavily" note with no
    # guard against exactly that failure mode: a handful of
    # disproportionately sci-fi entities in a 25-movie ranking pulling
    # the whole classification toward "Science Fiction" / "time travel"
    # instead of "movie ranking/listicle".
    SPARSE_LIST_ENTITY_THRESHOLD = 5
    sparse_note = ""
    if (
        structural_video_type in ("list", "ranking", "countdown", "compilation")
        and len(entities) < SPARSE_LIST_ENTITY_THRESHOLD
    ):
        sparse_note = (
            f" Only {len(entities)} candidate item(s) were identified, which is "
            "suspiciously few for this format — this most likely means extraction "
            "was incomplete (e.g. on-screen text not fully captured), NOT that the "
            "video is only about those items. Do NOT infer a narrow theme, genre, "
            "or sub-topic (e.g. a shared theme among just the visible items) from "
            "this small, likely-unrepresentative sample. Classify by the general "
            "list/ranking format itself and set confidence well below 0.5 to "
            "reflect the incomplete evidence."
        )

    structural_hint = (
        f"\nNOTE: This video has a strict structural layout: '{structural_video_type}'. "
        "Factor this format heavily into the child_category and intent — the "
        "child_category should identify it as a ranked list/countdown, and intent "
        f"should reflect browsing or discovering multiple ranked items.{sparse_note}\n"
        if structural_video_type != "none"
        else ""
    )

    return (
        "Classify this YouTube video into a taxonomy.\n\n"
        f"DOMINANT SUBJECT: {subject_str}\n"
        f"SUMMARY: {summary_str}\n"
        f"KEY ENTITIES: {entity_str}\n"
        f"{structural_hint}\n"
        "Respond ONLY with valid JSON (no markdown, no backticks):\n"
        "{\n"
        '  "parent_category": "Education|Shopping|Sports|Music|'
        'Film|Technology|Food|Health|News|Other",\n'
        '  "child_category": "specific subcategory within the parent",\n'
        '  "intent": "what the viewer gains by watching (one phrase)",\n'
        '  "confidence": 0.85\n'
        "}"
    )

def _call_groq(prompt: str, settings: Settings) -> str:
    """Call Groq API. Raises on failure — caller handles."""
    import httpx

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": GROQ_TAXONOMY_TEMPERATURE,
        "max_tokens": GROQ_TAXONOMY_MAX_TOKENS,
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
        return str(data["choices"][0]["message"]["content"])

def _parse_taxonomy_response(raw_json: str) -> GroqTaxonomyResult:
    """Parse Groq JSON response. Raises on malformed input."""
    import json

    data = json.loads(raw_json)
    parent = str(data.get("parent_category", "Other"))
    if parent not in VALID_PARENT_CATEGORIES:
        parent = "Other"
    child = str(data.get("child_category", "General"))
    intent = str(data.get("intent", "Watch and learn"))
    try:
        conf = float(data.get("confidence", 0.7))
        conf = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        conf = 0.7

    return GroqTaxonomyResult(
        parent_category=parent,
        child_category=child,
        intent=intent,
        confidence=conf,
        fallback_notes=[],
        groq_used=True,
    )

def _make_fallback_result(
    dominant_subject: str | None,
    has_speech: bool,
    has_music: bool,
    structural_video_type: str,
    note: str = "",
) -> TaxonomyFallback:
    """Rule-based fallback used when Groq is unavailable.

    Defers to intent_resolver for keyword-based mapping.
    Always returns a result — never raises.
    """
    from ytclfr.taxonomy.intent_resolver import resolve_by_rules

    result = resolve_by_rules(
        dominant_subject=dominant_subject,
        has_speech=has_speech,
        has_music=has_music,
        structural_video_type=structural_video_type,
    )
    if note:
        result.fallback_notes.append(note)
    return result
