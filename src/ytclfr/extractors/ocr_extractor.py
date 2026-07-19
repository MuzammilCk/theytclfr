"""Frame-level OCR text extraction via Tesseract (pytesseract).

Replaces the old PaddleOCR-based implementation: paddleocr was never
declared in pyproject.toml (only pytesseract was), so it was never
actually installed by a normal `pip install -e .` — every call
silently degraded to an empty result via the ImportError fallback,
regardless of how many frames were sampled or checked. pytesseract is
the dependency this project actually declares and installs; this
module makes the code match that.

Windows note: pytesseract is a thin wrapper that shells out to the
real Tesseract-OCR engine, which is a separate system install, not a
pip package. Install it from
https://github.com/UB-Mannheim/tesseract/wiki and either add it to
PATH or set pytesseract.pytesseract.tesseract_cmd to its install
path — otherwise this degrades exactly the same way paddleocr did.
"""
import numpy as np
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)


def extract_text_from_frame_v2(frame: np.ndarray) -> tuple[str, float]:
    """Extract text and average confidence (0.0-1.0) from a video frame.

    Never raises — on any failure (missing binary, corrupt frame,
    unexpected pytesseract output), returns ("", 0.0) so callers can
    treat "no text found" and "OCR unavailable" the same way.
    """
    try:
        import pytesseract
    except ImportError as exc:
        logger.error(f"pytesseract is not installed: {exc}")
        return "", 0.0

    try:
        data = pytesseract.image_to_data(frame, output_type=pytesseract.Output.DICT)
        words: list[str] = []
        confidences: list[float] = []
        for text, conf in zip(data.get("text", []), data.get("conf", [])):
            stripped = text.strip()
            try:
                conf_val = float(conf)
            except (TypeError, ValueError):
                continue
            if stripped and conf_val >= 0:
                words.append(stripped)
                confidences.append(conf_val)

        if not words:
            return "", 0.0

        full_text = " ".join(words)
        avg_conf = (sum(confidences) / len(confidences)) / 100.0
        return full_text, float(avg_conf)
    except Exception as exc:
        logger.error(f"Tesseract extraction failed: {exc}")
        return "", 0.0
