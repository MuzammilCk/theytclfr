"""Rule-based taxonomy fallback for Stage D.

Pure function — no Groq, no DB, no Celery.
Used when Groq is unavailable or fails.
Provides deterministic taxonomy classification from
keyword matching against dominant_subject.

All keyword sets are TUNABLE module-level constants.
"""
from dataclasses import dataclass, field

# ── TUNABLE CONSTANTS ──────────────────────────────────────

DEFAULT_CONFIDENCE: float = 0.55

# Maps lowercase keyword → (parent, child, intent)
SUBJECT_KEYWORD_MAP: dict[str, tuple[str, str, str]] = {
    # Education
    "tutorial":    ("Education",   "Tutorial",        "Learn a skill step by step"),
    "course":      ("Education",   "Course Lesson",   "Study the material"),
    "lecture":     ("Education",   "Lecture",         "Understand the concept"),
    "explained":   ("Education",   "Explainer",       "Understand the concept"),
    "lesson":      ("Education",   "Lesson",          "Study the material"),
    "how to":      ("Education",   "How-To Guide",    "Follow the instructions"),
    "guide":       ("Education",   "Guide",           "Follow the instructions"),
    # Technology
    "coding":      ("Technology",  "Coding Tutorial", "Write the code yourself"),
    "programming": ("Technology",  "Coding Tutorial", "Write the code yourself"),
    "python":      ("Technology",  "Coding Tutorial", "Write the code yourself"),
    "javascript":  ("Technology",  "Coding Tutorial", "Write the code yourself"),
    "react":       ("Technology",  "Coding Tutorial", "Write the code yourself"),
    "review":      ("Technology",  "Tech Review",     "Decide whether to buy or use"),
    "demo":        ("Technology",  "Product Demo",    "See it in action"),
    # Shopping
    "unboxing":    ("Shopping",    "Unboxing",        "Experience the reveal"),
    "haul":        ("Shopping",    "Haul",            "Discover what was bought"),
    "comparison":  ("Shopping",    "Comparison",      "Decide between options"),
    "best":        ("Shopping",    "Product Review",  "Discover top picks"),
    # Sports
    "highlights":  ("Sports",      "Highlights",      "Catch the best moments"),
    "match":       ("Sports",      "Match Recap",     "Watch the key moments"),
    "game":        ("Sports",      "Game Recap",      "Watch the key moments"),
    "analysis":    ("Sports",      "Analysis",        "Understand the tactics"),
    # Music
    "music video": ("Music",       "Music Video",     "Watch and listen"),
    "song":        ("Music",       "Song",            "Listen and enjoy"),
    "cover":       ("Music",       "Cover",           "Enjoy the rendition"),
    "playlist":    ("Music",       "Playlist",        "Discover new music"),
    # Film
    "movie":       ("Film",        "Movie Review",    "Decide whether to watch"),
    "film":        ("Film",        "Film Review",     "Decide whether to watch"),
    "recap":       ("Film",        "Recap",           "Catch up on the story"),
    "reaction":    ("Film",        "Reaction",        "Watch the genuine reaction"),
    # Food
    "recipe":      ("Food",        "Recipe",          "Cook along at home"),
    "cooking":     ("Food",        "Cooking Tutorial","Cook along at home"),
    "food":        ("Food",        "Food Content",    "Discover the dish"),
    # Health
    "workout":     ("Health",      "Workout",         "Exercise along"),
    "fitness":     ("Health",      "Fitness Guide",   "Improve your health"),
    "meditation":  ("Health",      "Wellness",        "Practice mindfulness"),
    # News
    "news":        ("News",        "News Report",     "Stay informed"),
    "update":      ("News",        "Update",          "Stay informed"),
    "breaking":    ("News",        "Breaking News",   "Learn what happened"),
}

# Signal-based defaults when no keyword matches
MUSIC_ONLY_DEFAULT: tuple[str, str, str] = (
    "Music", "Audio Content", "Listen and enjoy"
)
SPEECH_DEFAULT: tuple[str, str, str] = (
    "Education", "General Content", "Watch and learn"
)
NO_SIGNAL_DEFAULT: tuple[str, str, str] = (
    "Other", "General Video", "Watch the content"
)

# ── Output dataclass ───────────────────────────────────────

@dataclass
class TaxonomyFallback:
    parent_category: str
    child_category: str
    intent: str
    confidence: float
    fallback_notes: list[str] = field(default_factory=list)
    groq_used: bool = False

# ── Public function ─────────────────────────────────────────

def resolve_by_rules(
    dominant_subject: str | None,
    has_speech: bool,
    has_music: bool,
    structural_video_type: str = "none",
) -> TaxonomyFallback:
    """Classify video taxonomy using keyword rules.

    Searches SUBJECT_KEYWORD_MAP against the dominant_subject.
    Falls back to signal-based defaults if no keyword matches.

    Never raises. Always returns a TaxonomyFallback.

    Args:
        dominant_subject: EvidenceGraph.dominant_subject or None.
        has_speech: SignalManifest.has_speech.
        has_music: SignalManifest.has_music.

    Returns:
        TaxonomyFallback with groq_used=False.
    """
    notes: list[str] = ["Groq unavailable — rule-based taxonomy used"]

    if structural_video_type != "none":
        notes.append(f"Structural override applied: {structural_video_type}")
        if structural_video_type in ("list", "ranking", "countdown", "compilation"):
            return TaxonomyFallback(
                parent_category="Other",
                child_category=structural_video_type.capitalize(),
                intent="Consume structured content",
                confidence=DEFAULT_CONFIDENCE + 0.1,
                fallback_notes=notes,
                groq_used=False,
            )

    if dominant_subject:
        subject_lower = dominant_subject.lower()
        for keyword, (parent, child, intent) in SUBJECT_KEYWORD_MAP.items():
            if keyword in subject_lower:
                return TaxonomyFallback(
                    parent_category=parent,
                    child_category=child,
                    intent=intent,
                    confidence=DEFAULT_CONFIDENCE,
                    fallback_notes=notes,
                    groq_used=False,
                )

    # Signal-based fallback
    if has_music and not has_speech:
        parent, child, intent = MUSIC_ONLY_DEFAULT
    elif has_speech:
        parent, child, intent = SPEECH_DEFAULT
    else:
        parent, child, intent = NO_SIGNAL_DEFAULT

    notes.append("No subject keyword matched — signal-based default used")
    return TaxonomyFallback(
        parent_category=parent,
        child_category=child,
        intent=intent,
        confidence=DEFAULT_CONFIDENCE * 0.7,
        fallback_notes=notes,
        groq_used=False,
    )
