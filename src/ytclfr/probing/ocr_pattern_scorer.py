"""Scans timestamped text segments for ordinal and countdown patterns.

Despite the historical name, this only ever looks at plain `.text` /
`.timestamp` pairs — nothing here is OCR-specific. It was written and
tested against OCR segments (Stage C calls it right after OCR
extraction, before alignment and taxonomy mapping) but works
identically against ASR segments: a purely spoken list ("...coming in
at number three...") produces the same kind of decreasing-number
sequence as an on-screen "#3" countdown card, just carried in `.text`
transcribed from speech instead of read off a frame.
"""
import re
from dataclasses import dataclass
from typing import Any

# Regex to match ordinals (e.g., "1.", "#1", "Number 1", "10", "Top 10")
ORDINAL_PATTERN = re.compile(
    r"(?:^|\s)(?:#\d+|\d+\.|number\s*\d+|top\s*\d+|\d+)(?:\s|$)", 
    re.IGNORECASE
)

@dataclass
class OrdinalPatternResult:
    ordinal_pattern_score: float
    countdown_likelihood: float


def score_ordinal_patterns(segments_in: list[Any]) -> OrdinalPatternResult:
    """Scans text segments (OCR or ASR) for structural patterns.
    
    Args:
        segments_in: List of segment objects or dicts (OCR or ASR)
            which must have a 'text' and 'timestamp' attribute/key.
            
    Returns:
        OrdinalPatternResult with calculated scores 0.0 to 1.0.
    """
    if not segments_in:
        return OrdinalPatternResult(0.0, 0.0)

    # Convert to standard format
    segments = []
    for s in segments_in:
        text = s.text if hasattr(s, 'text') else s.get('text', '')
        ts = s.timestamp if hasattr(s, 'timestamp') else s.get('timestamp', 0.0)
        segments.append({"text": str(text).strip(), "timestamp": float(ts)})

    # Sort by timestamp
    segments.sort(key=lambda x: x["timestamp"])

    matched_numbers = []
    for s in segments:
        text = s["text"]
        # Find all number-like matches
        matches = re.findall(r'\d+', text)
        if matches:
            # We just take the first number found in the segment for sequence checking
            try:
                num = int(matches[0])
                # Only care about reasonable ranking numbers (1-100)
                if 1 <= num <= 100:
                    matched_numbers.append(num)
            except ValueError:
                pass

    if not matched_numbers:
        return OrdinalPatternResult(0.0, 0.0)

    # 1. Ordinal Pattern Score (density of numbers across segments)
    # If 20% of segments have numbers, that's a strong ordinal pattern.
    density = len(matched_numbers) / len(segments)
    # Scale density so 20% coverage -> 1.0 score
    ordinal_score = min(density * 5.0, 1.0)
    
    # 2. Countdown Likelihood (detecting decreasing sequences)
    # Check if numbers tend to go down (e.g., 10, 9, 8, ... 1)
    decrements = 0
    increments = 0
    for i in range(1, len(matched_numbers)):
        if matched_numbers[i] < matched_numbers[i-1]:
            decrements += 1
        elif matched_numbers[i] > matched_numbers[i-1]:
            increments += 1

    countdown_score = 0.0
    if len(matched_numbers) >= 3:
        if decrements > increments:
            countdown_score = min(decrements / (len(matched_numbers) - 1) * 1.5, 1.0)

    return OrdinalPatternResult(
        ordinal_pattern_score=round(ordinal_score, 3),
        countdown_likelihood=round(countdown_score, 3)
    )
