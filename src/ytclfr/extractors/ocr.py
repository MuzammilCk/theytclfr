import subprocess
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from ytclfr.contracts.extractor import (
    ExtractorResult,
    OCRSegment,
)
from ytclfr.core.config import Settings
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)


class OCRExtractor:
    """Extracts on-screen text from video frames
    via ffmpeg frame extraction + Tesseract OCR.

    Uses settings.ocr_frame_sample_rate to determine
    how many frames per second to sample.
    Uses settings.tesseract_cmd_path for binary location.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _extract_frames(
        self,
        video_path: Path,
        output_dir: Path,
        fps: int,
    ) -> list[tuple[Path, float]]:
        """Extract frames at given FPS using ffmpeg.

        Returns list of (frame_path, timestamp_seconds).
        Uses encoding="utf-8", errors="replace",
        timeout=300 (5 min max for long videos).
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        pattern = str(output_dir / "frame_%06d.jpg")

        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            f"fps={fps}",
            "-q:v",
            "2",
            "-y",
            pattern,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if result.returncode != 0:
            logger.warning(
                "ffmpeg frame extraction returned non-zero exit code: %s",
                result.stderr[:500],
            )

        frames: list[tuple[Path, float]] = []
        for frame_path in sorted(output_dir.glob("frame_*.jpg")):
            # Calculate timestamp from filename index
            # ffmpeg names frames frame_000001.jpg etc
            # starting at frame 1.
            idx_str = frame_path.stem.split("_")[-1]
            try:
                frame_index = int(idx_str)
                timestamp = (frame_index - 1) / fps
                frames.append((frame_path, timestamp))
            except ValueError:
                continue
        return frames

    def _ocr_single_frame(self, frame_path: Path) -> tuple[str, float]:
        """Run Tesseract on a single frame.

        Returns (text, confidence). Confidence is 0.0
        if Tesseract returns no data.
        """
        import pytesseract
        from PIL import Image

        if self._settings.tesseract_cmd_path != "tesseract":
            pytesseract.pytesseract.tesseract_cmd = self._settings.tesseract_cmd_path

        try:
            img = Image.open(frame_path)
            data = pytesseract.image_to_data(
                img,
                output_type=pytesseract.Output.DICT,
            )
            texts = []
            confs = []
            for i, conf_val in enumerate(data["conf"]):
                try:
                    conf_float = float(conf_val)
                except (ValueError, TypeError):
                    continue
                if conf_float > 0:
                    word = data["text"][i].strip()
                    if word:
                        texts.append(word)
                        confs.append(conf_float)
            full_text = " ".join(texts).strip()
            avg_conf = sum(confs) / len(confs) / 100.0 if confs else 0.0
            return full_text, round(avg_conf, 4)
        except Exception as exc:
            logger.debug(
                "OCR failed on frame %s: %s",
                frame_path.name,
                exc,
            )
            return "", 0.0

    def _deduplicate_segments(
        self,
        segments: list[OCRSegment],
    ) -> list[OCRSegment]:
        """Remove consecutive duplicate OCR texts.

        Static on-screen overlays appear in every frame.
        Deduplicate by comparing normalized text to the
        previous segment.
        """
        if not segments:
            return []
        deduplicated: list[OCRSegment] = [segments[0]]
        for seg in segments[1:]:
            prev_text = deduplicated[-1].text.strip().lower()
            curr_text = seg.text.strip().lower()
            if curr_text and curr_text != prev_text:
                deduplicated.append(seg)
        return deduplicated

    def extract(
        self,
        job_id: UUID,
        video_path: Path,
        output_dir: Path,
    ) -> ExtractorResult:
        """Extract on-screen text from all sampled frames.

        Args:
            job_id: UUID of the job being processed.
            video_path: Path to the downloaded video file.
            output_dir: Directory for extracted frames.
                        Created if it does not exist.

        Returns:
            ExtractorResult with extractor_type="ocr".
        """
        fps = self._settings.ocr_frame_sample_rate

        frames = self._extract_frames(video_path, output_dir, fps)

        ocr_segments: list = []  # type: ignore
        for frame_path, timestamp in frames:
            text, confidence = self._ocr_single_frame(frame_path)
            if text:
                ocr_segments.append(
                    OCRSegment(
                        segment_type="ocr",
                        frame_timestamp=round(timestamp, 3),
                        text=text,
                        confidence=confidence,
                        bounding_boxes=None,
                    )
                )

        deduplicated = self._deduplicate_segments(
            ocr_segments
        )
        # Estimate duration from last frame timestamp
        total_duration = frames[-1][1] if frames else 0.0

        return ExtractorResult(
            job_id=job_id,
            extractor_type="ocr",
            segments=deduplicated,  # type: ignore[arg-type]
            total_duration_seconds=round(total_duration, 3),
            extracted_at=datetime.now(UTC),
            error=None,
        )





@lru_cache(maxsize=1)
def get_ocr_extractor() -> OCRExtractor:
    from ytclfr.core.config import get_settings
    return OCRExtractor(get_settings())
