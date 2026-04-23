from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from ytclfr.contracts.extractor import (
    ASRSegment,
    ExtractorResult,
)
from ytclfr.core.config import Settings
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)


class ASRExtractor:
    """Transcribes video audio using faster-whisper.

    Loaded once per worker process — do not instantiate
    per-task. Use as a singleton via lru_cache in the
    Celery task wrapper.
    """

    def __init__(self, settings: Settings) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        self._settings = settings
        logger.info(
            "ASRExtractor initialized.",
            extra={
                "model": settings.whisper_model_size,
                "device": settings.whisper_device,
                "compute_type": settings.whisper_compute_type,
            },
        )

    def extract(
        self,
        job_id: UUID,
        video_path: Path,
    ) -> ExtractorResult:
        """Transcribe video audio with word-level timestamps.

        Args:
            job_id: UUID of the job being processed.
            video_path: Path to the downloaded video file.

        Returns:
            ExtractorResult with extractor_type="asr" and
            a list of ASRSegment objects.

        Raises:
            Exception: Any faster-whisper error propagates
            up to the Celery task for retry handling.
        """
        segments_raw, info = self._model.transcribe(
            str(video_path),
            word_timestamps=True,
            beam_size=5,
        )

        asr_segments: list = []  # type: ignore
        for seg in segments_raw:
            words_data: list = []  # type: ignore
            if seg.words:
                for word in seg.words:
                    words_data.append(
                        {
                            "word": word.word,
                            "start": round(word.start, 3),
                            "end": round(word.end, 3),
                            "probability": round(word.probability, 4),
                        }
                    )
            asr_segments.append(
                ASRSegment(
                    segment_type="asr",
                    start_time=round(seg.start, 3),
                    end_time=round(seg.end, 3),
                    text=seg.text.strip(),
                    confidence=round(
                        max(
                            0.0,
                            min(1.0, float(getattr(seg, "avg_logprob", -0.5)) + 1.0),
                        ),
                        4,
                    ),
                    words=words_data,
                )
            )

        return ExtractorResult(
            job_id=job_id,
            extractor_type="asr",
            segments=asr_segments,
            total_duration_seconds=round(info.duration, 3),
            extracted_at=datetime.now(UTC),
            error=None,
        )


@lru_cache(maxsize=1)
def get_asr_extractor() -> ASRExtractor:
    from ytclfr.core.config import get_settings

    return ASRExtractor(get_settings())
