from unittest.mock import patch
from uuid import uuid4

from ytclfr.core.config import Settings
from ytclfr.extractors.ocr import OCRExtractor


def test_ocr_extract_returns_extractor_result(tmp_path):
    settings = Settings(ocr_frame_sample_rate=1, tesseract_cmd_path="tesseract")
    extractor = OCRExtractor(settings)

    with patch.object(extractor, "_extract_frames") as mock_extract:
        mock_extract.return_value = [
            (tmp_path / "frame_000001.jpg", 0.0),
            (tmp_path / "frame_000002.jpg", 1.0),
        ]
        with patch.object(extractor, "_ocr_single_frame") as mock_ocr:
            mock_ocr.side_effect = [("Sample text", 0.9), ("Other text", 0.8)]

            job_id = uuid4()
            result = extractor.extract(job_id, tmp_path / "video.mp4", tmp_path)

            assert result.extractor_type == "ocr"
            assert len(result.segments) == 2
            assert result.segments[0].text == "Sample text"


def test_ocr_deduplicates_identical_consecutive_frames(tmp_path):
    settings = Settings()
    extractor = OCRExtractor(settings)

    with patch.object(extractor, "_extract_frames") as mock_extract:
        mock_extract.return_value = [
            (tmp_path / "frame_000001.jpg", 0.0),
            (tmp_path / "frame_000002.jpg", 1.0),
            (tmp_path / "frame_000003.jpg", 2.0),
        ]
        with patch.object(extractor, "_ocr_single_frame") as mock_ocr:
            mock_ocr.side_effect = [
                ("Same text", 0.9),
                ("Same text", 0.9),
                ("Same text", 0.9),
            ]

            result = extractor.extract(uuid4(), tmp_path / "video.mp4", tmp_path)
            assert len(result.segments) == 1


def test_ocr_handles_empty_frame_directory(tmp_path):
    settings = Settings()
    extractor = OCRExtractor(settings)

    with patch.object(extractor, "_extract_frames") as mock_extract:
        mock_extract.return_value = []

        result = extractor.extract(uuid4(), tmp_path / "video.mp4", tmp_path)
        assert len(result.segments) == 0


def test_ocr_skips_empty_text_frames(tmp_path):
    settings = Settings()
    extractor = OCRExtractor(settings)

    with patch.object(extractor, "_extract_frames") as mock_extract:
        mock_extract.return_value = [
            (tmp_path / "frame_000001.jpg", 0.0),
            (tmp_path / "frame_000002.jpg", 1.0),
        ]
        with patch.object(extractor, "_ocr_single_frame") as mock_ocr:
            mock_ocr.side_effect = [("", 0.0), ("Valid text", 0.8)]

            result = extractor.extract(uuid4(), tmp_path / "video.mp4", tmp_path)
            assert len(result.segments) == 1
            assert result.segments[0].text == "Valid text"
