import shutil
import time
from pathlib import Path
from uuid import UUID

from ytclfr.core.config import Settings
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)


class TempStorageManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_path = Path(settings.temp_media_path)

    def get_job_dir(self, job_id: UUID) -> Path:
        job_dir = self.base_path / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def cleanup_job(self, job_id: UUID) -> None:
        job_dir = self.base_path / str(job_id)
        if not job_dir.exists():
            logger.warning(f"Cleanup failed, directory does not exist: {job_dir}")
            return

        try:
            shutil.rmtree(job_dir)
        except Exception as e:
            logger.error(f"Failed to delete {job_dir}: {e}")

    def cleanup_expired(self) -> int:
        count = 0
        if not self.base_path.exists():
            return count

        now = time.time()
        for job_dir in self.base_path.iterdir():
            if not job_dir.is_dir():
                continue

            try:
                mtime = job_dir.stat().st_mtime
                if now - mtime > self.settings.temp_media_max_age_seconds:
                    shutil.rmtree(job_dir)
                    count += 1
            except Exception as e:
                logger.error(f"Failed to cleanup expired directory {job_dir}: {e}")

        return count
