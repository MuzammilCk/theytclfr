import numpy as np
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)

_paddle_ocr_instance = None

def _get_ocr():
    global _paddle_ocr_instance
    if _paddle_ocr_instance is None:
        try:
            from paddleocr import PaddleOCR
            # Singleton pattern
            _paddle_ocr_instance = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
        except ImportError as e:
            logger.error(f"PaddleOCR is not installed or failed to import: {e}")
            raise
    return _paddle_ocr_instance

def extract_text_from_frame_v2(frame: np.ndarray) -> tuple[str, float]:
    """Extract text and confidence using PaddleOCR."""
    try:
        ocr = _get_ocr()
    except ImportError:
        return "", 0.0

    try:
        results = ocr.ocr(frame, cls=True)
        if not results or not results[0]:
            return "", 0.0
            
        texts = []
        confidences = []
        for line in results[0]:
            # line is like [[box], (text, confidence)]
            _, (text, conf) = line
            texts.append(text)
            confidences.append(conf)
            
        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return full_text, float(avg_conf)
    except Exception as e:
        logger.error(f"PaddleOCR extraction failed: {e}")
        return "", 0.0
