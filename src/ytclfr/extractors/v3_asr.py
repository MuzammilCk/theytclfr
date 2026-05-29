from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from ytclfr.contracts.v3.bundle import ASRSegment, ASRCompletenessMetrics
from ytclfr.core.config import Settings
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)

class V3ASRExtractor:
    def __init__(self, settings: Settings) -> None:
        from faster_whisper import WhisperModel
        self._model = WhisperModel(
            settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            cpu_threads=4,
        )
        self._settings = settings

    def extract(self, job_id: UUID, video_path: Path) -> tuple[list[ASRSegment], ASRCompletenessMetrics, float]:
        """Transcribe and compute VAD-to-Transcription Yield Heuristic."""
        # 1. Run Silero VAD directly to get VAD speech segments
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import VadOptions, get_speech_timestamps
        audio = decode_audio(str(video_path))
        vad_options = VadOptions(min_silence_duration_ms=500)
        vad_segments = get_speech_timestamps(audio, vad_options=vad_options)
        
        total_vad_speech_ms = 0.0
        # vad_segments returns dict with 'start' and 'end' in samples. default sample rate is 16000
        for seg in vad_segments:
            total_vad_speech_ms += ((seg['end'] - seg['start']) / 16000.0) * 1000.0
            
        # 2. Run Whisper transcription
        segments_raw, info = self._model.transcribe(
            str(video_path),
            word_timestamps=True,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        asr_segments: list[ASRSegment] = []
        total_transcribed_ms = 0.0
        
        for seg in segments_raw:
            words_data: list = []
            if seg.words:
                for word in seg.words:
                    word_duration_ms = (word.end - word.start) * 1000.0
                    total_transcribed_ms += word_duration_ms
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
                    confidence=round(max(0.0, min(1.0, float(getattr(seg, "avg_logprob", -0.5)) + 1.0)), 4),
                    words=words_data,
                )
            )

        # Compute heuristic metrics
        untranscribed_speech_ratio = 1.0 - (total_transcribed_ms / max(total_vad_speech_ms, 1.0))
        if total_vad_speech_ms == 0:
            untranscribed_speech_ratio = 0.0
            
        untranscribed_speech_ratio = max(0.0, min(1.0, untranscribed_speech_ratio))
        
        # Check max untranscribed segment
        max_untranscribed_segment_ms = 0.0
        for vad_seg in vad_segments:
            v_start = vad_seg['start'] / 16000.0
            v_end = vad_seg['end'] / 16000.0
            v_duration_ms = (v_end - v_start) * 1000.0
            
            # Check if this VAD segment has any transcribed words overlapping it
            has_words = False
            for seg in asr_segments:
                if seg.end_time > v_start and seg.start_time < v_end:
                    has_words = True
                    break
            if not has_words:
                max_untranscribed_segment_ms = max(max_untranscribed_segment_ms, v_duration_ms)
                
        is_degraded = untranscribed_speech_ratio > 0.3 or max_untranscribed_segment_ms > 2500.0
        
        metrics = ASRCompletenessMetrics(
            total_vad_speech_ms=round(total_vad_speech_ms, 2),
            total_transcribed_ms=round(total_transcribed_ms, 2),
            untranscribed_speech_ratio=round(untranscribed_speech_ratio, 3),
            max_untranscribed_segment_ms=round(max_untranscribed_segment_ms, 2),
            is_degraded=is_degraded,
        )
        
        return asr_segments, metrics, round(info.duration, 3)

@lru_cache(maxsize=1)
def get_v3_asr_extractor() -> V3ASRExtractor:
    from ytclfr.core.config import get_settings
    return V3ASRExtractor(get_settings())
