from unittest.mock import MagicMock, patch
from uuid import uuid4

from ytclfr.core.config import Settings
from ytclfr.extractors.asr import ASRExtractor, get_asr_extractor


def test_asr_extract_returns_extractor_result():
    settings = Settings(
        whisper_model_size="tiny", whisper_device="cpu", whisper_compute_type="int8"
    )
    with patch("faster_whisper.WhisperModel") as mock_model_cls:
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model

        mock_info = MagicMock()
        mock_info.duration = 10.0

        mock_word = MagicMock()
        mock_word.word = "test"
        mock_word.start = 0.1
        mock_word.end = 0.5
        mock_word.probability = 0.99

        mock_seg1 = MagicMock()
        mock_seg1.start = 0.0
        mock_seg1.end = 1.0
        mock_seg1.text = "segment one"
        mock_seg1.avg_logprob = -0.5
        mock_seg1.words = [mock_word]

        mock_seg2 = MagicMock()
        mock_seg2.start = 1.0
        mock_seg2.end = 2.0
        mock_seg2.text = "segment two"
        mock_seg2.avg_logprob = -0.2
        mock_seg2.words = [mock_word]

        mock_seg3 = MagicMock()
        mock_seg3.start = 2.0
        mock_seg3.end = 3.0
        mock_seg3.text = "segment three"
        mock_seg3.avg_logprob = -0.1
        mock_seg3.words = [mock_word]

        mock_model.transcribe.return_value = (
            [mock_seg1, mock_seg2, mock_seg3],
            mock_info,
        )

        extractor = ASRExtractor(settings)
        job_id = uuid4()
        result = extractor.extract(job_id, "fake_video.mp4")

        assert result.extractor_type == "asr"
        assert len(result.segments) == 3
        assert result.error is None
        for s in result.segments:
            assert s.segment_type == "asr"


def test_asr_segment_confidence_clamped_to_valid_range():
    settings = Settings(
        whisper_model_size="tiny", whisper_device="cpu", whisper_compute_type="int8"
    )
    with patch("faster_whisper.WhisperModel") as mock_model_cls:
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model

        mock_info = MagicMock()
        mock_info.duration = 5.0

        mock_seg = MagicMock()
        mock_seg.start = 0.0
        mock_seg.end = 1.0
        mock_seg.text = "test"
        mock_seg.avg_logprob = -2.0  # +1.0 = -1.0 -> should clamp to 0.0
        mock_seg.words = []

        mock_model.transcribe.return_value = ([mock_seg], mock_info)

        extractor = ASRExtractor(settings)
        result = extractor.extract(uuid4(), "fake_video.mp4")
        assert result.segments[0].confidence >= 0.0
        assert result.segments[0].confidence == 0.0


def test_asr_extractor_singleton_via_lru_cache():
    with patch("faster_whisper.WhisperModel"):
        extractor1 = get_asr_extractor()
        extractor2 = get_asr_extractor()
        assert extractor1 is extractor2
