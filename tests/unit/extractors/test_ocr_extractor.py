"""Tests for extractors/ocr_extractor.py (Tesseract-based, replacing
the never-installable paddleocr implementation).
"""
import numpy as np
from ytclfr.extractors.ocr_extractor import extract_text_from_frame_v2


def test_extract_text_real_tesseract_call():
    """Sanity check against the real installed tesseract binary — this
    is the exact gap that silently swallowed every OCR call before:
    if the engine isn't actually available, this test itself would
    fail loudly instead of a downstream stage quietly getting nothing."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 80), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 20), "Top 25", fill="black")
    frame = np.array(img)

    text, conf = extract_text_from_frame_v2(frame)

    assert "Top" in text or "25" in text
    assert 0.0 <= conf <= 1.0


def test_extract_text_blank_frame_returns_empty(mocker):
    mock_pytesseract = mocker.patch("pytesseract.image_to_data")
    mock_pytesseract.return_value = {"text": ["", "", ""], "conf": [-1, -1, -1]}

    text, conf = extract_text_from_frame_v2(np.zeros((50, 50, 3), dtype=np.uint8))

    assert text == ""
    assert conf == 0.0


def test_extract_text_averages_confidence_and_filters_noise(mocker):
    mock_pytesseract = mocker.patch("pytesseract.image_to_data")
    mock_pytesseract.return_value = {
        "text": ["", "Top", "25", ""],
        "conf": [-1, 80, 60, -1],  # non-text layout boxes have conf=-1
    }

    text, conf = extract_text_from_frame_v2(np.zeros((50, 50, 3), dtype=np.uint8))

    assert text == "Top 25"
    assert conf == 0.7  # (80 + 60) / 2 / 100


def test_missing_tesseract_binary_degrades_gracefully(mocker):
    mock_pytesseract = mocker.patch("pytesseract.image_to_data")
    mock_pytesseract.side_effect = RuntimeError(
        "tesseract is not installed or it's not in your PATH"
    )

    text, conf = extract_text_from_frame_v2(np.zeros((50, 50, 3), dtype=np.uint8))

    assert text == ""
    assert conf == 0.0


def test_missing_pytesseract_package_degrades_gracefully(mocker):
    mocker.patch.dict("sys.modules", {"pytesseract": None})

    text, conf = extract_text_from_frame_v2(np.zeros((50, 50, 3), dtype=np.uint8))

    assert text == ""
    assert conf == 0.0
