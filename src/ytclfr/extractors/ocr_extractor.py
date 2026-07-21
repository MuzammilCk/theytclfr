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
import cv2
import numpy as np
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)

# ── TUNABLE CONSTANTS ───────────────────────────────────────────────
OCR_UPSCALE_TARGET_HEIGHT: int = 720
# Tesseract's own 0-100 per-word confidence. Averaging over *every*
# returned token (the old behaviour) let a handful of confident real
# words drag a majority of low-confidence noise glyphs — texture and
# gradients Tesseract misreads as characters — over the line. Filtering
# per word instead of per frame keeps genuine captions and drops noise.
OCR_WORD_MIN_CONFIDENCE: float = 45.0
OCR_WORD_MIN_ALNUM_CHARS: int = 2

_tesseract_cmd_configured = False


def _configure_tesseract_cmd(pytesseract_module) -> None:
    """Point pytesseract at the configured Tesseract binary, once.

    `Settings.tesseract_cmd_path` existed but was never applied here —
    on a machine where the `tesseract` binary isn't already on PATH
    (the Windows case this module's docstring warns about), every call
    degraded straight to the except-branch below with no way to
    configure around it. get_settings() is itself lru_cached, but we
    still only want to touch pytesseract's global config once.
    """
    global _tesseract_cmd_configured
    if _tesseract_cmd_configured:
        return
    try:
        from ytclfr.core.config import get_settings
        cmd_path = get_settings().tesseract_cmd_path
        if cmd_path:
            pytesseract_module.pytesseract.tesseract_cmd = cmd_path
    except Exception as exc:
        logger.warning(f"Could not apply tesseract_cmd_path setting: {exc}")
    _tesseract_cmd_configured = True


def _preprocess_for_ocr(frame: np.ndarray) -> np.ndarray:
    """Improve odds of detecting bold, stylized on-screen captions.

    Raw video frames — busy/photographic backgrounds, small caption
    height relative to frame size — are a poor match for Tesseract's
    default page-OCR assumptions. Otsu thresholding isolates
    high-contrast caption strokes from the background; since Otsu is
    polarity-agnostic (it may leave light text on a dark background,
    which Tesseract reads poorly), we detect that case and invert back
    to dark-text-on-light. Upscaling gives small caption text more
    pixels to work with.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    if h < OCR_UPSCALE_TARGET_HEIGHT:
        scale = OCR_UPSCALE_TARGET_HEIGHT / h
        gray = cv2.resize(
            gray, (int(w * scale), OCR_UPSCALE_TARGET_HEIGHT),
            interpolation=cv2.INTER_CUBIC,
        )
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if cv2.countNonZero(thresh) < thresh.size / 2:
        thresh = cv2.bitwise_not(thresh)
    return thresh


def _is_probably_real_word(word: str) -> bool:
    """Drop single-glyph OCR noise from busy/photographic backgrounds.

    Tesseract on unstructured imagery frequently "reads" short
    punctuation-only or single-character fragments out of texture and
    gradients. Requiring 2+ alphanumeric characters filters most of
    that without discarding genuine short tokens (e.g. rank numbers).
    """
    return sum(1 for ch in word if ch.isalnum()) >= OCR_WORD_MIN_ALNUM_CHARS


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

    _configure_tesseract_cmd(pytesseract)

    try:
        processed = _preprocess_for_ocr(frame)
        # PSM 11 ("sparse text, no particular order") fits scattered
        # caption/title-card overlays far better than the default PSM 3,
        # which assumes a single document-like block of text and was
        # missing real on-screen text on this style of content.
        data = pytesseract.image_to_data(
            processed, config="--psm 11", output_type=pytesseract.Output.DICT,
        )
        words: list[str] = []
        confidences: list[float] = []
        for text, conf in zip(data.get("text", []), data.get("conf", [])):
            stripped = text.strip()
            try:
                conf_val = float(conf)
            except (TypeError, ValueError):
                continue
            if (
                stripped
                and conf_val >= OCR_WORD_MIN_CONFIDENCE
                and _is_probably_real_word(stripped)
            ):
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
